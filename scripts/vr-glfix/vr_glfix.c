/* libvr_glfix.dylib -- point MoltenVR/OpenVR's statically bound GL calls at Mesa.
 *
 * THE BUG
 * libopenvr_api.dylib (MoltenVR's runtime shim) declares OpenGL.framework as an
 * LC_LOAD_DYLIB, so each of its 25 _gl* imports is a two-level-namespace bind
 * whose target dylib is named in the bind opcode. Two-level binds never consult
 * the flat namespace and never go through dlsym(), so neither of the two
 * redirection mechanisms already in the stack can touch them:
 *
 *   - libgl_interpose.dylib interposes dlsym only. It redirects clients that
 *     call dlsym("glFoo") at runtime, which is what LWJGL does. It cannot
 *     affect a statically bound import.
 *   - the search path. Apple's OpenGL is named explicitly, so DYLD_LIBRARY_PATH
 *     ordering is irrelevant.
 *
 * When no CGL context is current -- the normal case, because LWJGL made an EGL
 * context current for Mesa, not a CGL one -- the shim's CPU-readback fallback
 * path deliberately calls Apple's glGenBuffers, which dereferences a null CGL
 * context and dies with SIGSEGV.
 *
 * THE FIX
 * Interpose those 25 names ourselves and forward each call to Mesa. Mesa's
 * libGL.dylib is a thin wrapper that exports only ~39 symbols, so dlsym and
 * glXGetProcAddress both come up empty for most of them. The route that works is
 * Mesa's eglGetProcAddress -- exactly the one libgl_interpose already
 * discovered -- because it reaches the driver's dispatch table rather than the
 * library's export list.
 *
 * NO RECURSION
 * Forwarding targets are resolved from the Mesa libEGL handle only, never from
 * RTLD_DEFAULT. RTLD_DEFAULT would find our own replacements (we interpose
 * these exact names) and every call would recurse into itself.
 *
 * THE TRAMPOLINE NAMES MATTER
 * Each interpose tuple is {&redirect_glFoo, &glFoo}. If the trampoline were
 * named glFoo, the second operand would bind to the trampoline instead of to the
 * OpenGL.framework import, every tuple would collapse to {self, self}, and the
 * library would load cleanly and silently do nothing. Hence the redirect_ prefix,
 * and hence the build-time check the tool runs before it will install this file:
 * otool must report a 400-byte __interpose section (25 tuples x 16 bytes), nm must
 * report exactly 25 T _redirect_gl symbols, no U _CGL symbol may appear, and the
 * file must be code-signed. The same check, and what each failure means, is
 * documented in scripts/README.md.
 *
 * NOT INTERPOSED, ON PURPOSE
 *   _CGLGetCurrentContext  the shim's path probe must keep reporting NULL, or it
 *                          would take the zero-copy branch it cannot service
 *                          under Mesa. That NULL is precisely what selects the
 *                          fallback path this library exists to make survivable.
 *   _CGLTexImageIOSurface2D
 *                          Apple-only API with no Mesa equivalent. Leaving it
 *                          bound to OpenGL.framework keeps a genuine Apple GL
 *                          context working.
 *
 * BUILD (arm64, thin; must link OpenGL.framework or dyld rejects the tuples,
 * and must be ad-hoc signed or it will not load):
 *   xcrun clang -arch arm64 -O2 -Wall -Wextra -dynamiclib \
 *       -install_name @rpath/libvr_glfix.dylib \
 *       -framework OpenGL vr_glfix.c -o libvr_glfix.dylib
 *   codesign --force --sign - libvr_glfix.dylib
 *
 * DEPLOY + LOAD
 *   cp libvr_glfix.dylib "$STACK/vr-lib/"
 * and append it to the instance's PrismLauncher WrapperCommand:
 *   DYLD_INSERT_LIBRARIES="$STACK/vr-lib/libgl_interpose.dylib:$STACK/vr-lib/libvr_glfix.dylib"
 *
 * VERIFY BEFORE TRUSTING IT
 * glmtlmc option 4 runs all four of these on a build in a temporary directory
 * before copying it into vr-lib, and refuses to install a file that fails any of
 * them, because the failure mode is a dylib that loads and does nothing:
 *   otool -arch arm64 -l libvr_glfix.dylib | grep -A6 __interpose   # size 0x190
 *   nm -arch arm64 libvr_glfix.dylib | grep -c 'T _redirect_gl'     # 25
 *   nm -arch arm64 libvr_glfix.dylib | grep -cE ' U _CGL'          # 0
 *   codesign -dv libvr_glfix.dylib                                  # Signature=adhoc
 * See scripts/README.md for what each number proves and how to check a build by
 * hand.
 *
 * MESA EGL LOCATION
 * Defaults to ../lib/libEGL.dylib relative to this dylib itself: the bundle
 * ships it in <stack>/vr-lib/ beside Mesa's <stack>/lib/, so that is Mesa's
 * EGL wherever the bundle is placed, and nothing about the machine that
 * assembled the bundle is recorded here. Override with the VRGLFIX_MESA_EGL
 * environment variable to point at a different build.
 */

#define GL_SILENCE_DEPRECATION 1
#include <OpenGL/gl.h>
#include <dlfcn.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define VRGLFIX_LOG_PREFIX "vrglfix: "

/*
 * One interpose tuple, in the order dyld expects: which implementation to use,
 * and which symbol it displaces. The section is emitted as __DATA,__interpose;
 * ld64 promotes it to __DATA_CONST, which dyld also reads.
 */
#define DYLD_INTERPOSE(_replacement, _replacee)                                   \
  __attribute__((used)) static struct {                                           \
    const void *replacement;                                                      \
    const void *replacee;                                                         \
  } _interpose_##_replacee __attribute__((section("__DATA,__interpose"))) = {    \
      (const void *)(unsigned long)&_replacement,                                 \
      (const void *)(unsigned long)&_replacee};

/* ------------------------------------------------------------------ */
/* Mesa resolution                                                     */
/* ------------------------------------------------------------------ */

typedef void *(*egl_get_proc_address_t)(const char *);

static void *mesaEglHandle = NULL;
static egl_get_proc_address_t mesaEglGetProcAddress = NULL;
static pthread_once_t mesaOnce = PTHREAD_ONCE_INIT;
static pthread_mutex_t logLock = PTHREAD_MUTEX_INITIALIZER;

static void logLine(const char *format, ...) {
  va_list args;

  pthread_mutex_lock(&logLock);
  va_start(args, format);
  fprintf(stderr, VRGLFIX_LOG_PREFIX);
  vfprintf(stderr, format, args);
  fprintf(stderr, "\n");
  va_end(args);
  fflush(stderr);
  pthread_mutex_unlock(&logLock);
}

/*
 * Mesa's EGL as this package ships it: vr-lib/ (this dylib's directory) and
 * lib/ are siblings inside the stack, so Mesa's EGL is always
 * ../lib/libEGL.dylib relative to this image, wherever the user puts the
 * bundle. Resolved from the dylib's own load path rather than from a prefix
 * recorded at build time, which would name the machine that assembled the
 * bundle. The buffer is static because resolveMesaEgl keeps the pointer;
 * it runs exactly once, under its pthread_once.
 */
static const char *mesaEglPathBesideSelf(void) {
  static char path[PATH_MAX];
  Dl_info self;
  const char *lastSeparator;
  int written;

  /*
   * dladdr names the image any address of ours was loaded from; taking
   * logLine's address here also forces the compiler to emit it, however
   * -O2 feels about inlining it.
   */
  if (dladdr((const void *)&logLine, &self) == 0 || self.dli_fname == NULL) {
    logLine("FATAL dladdr cannot name this dylib's own path; set "
            "VRGLFIX_MESA_EGL to point at Mesa's libEGL.dylib");
    return NULL;
  }

  /* A path with no directory in it cannot have a sibling beside it. */
  lastSeparator = strrchr(self.dli_fname, '/');
  if (lastSeparator == NULL) {
    logLine("FATAL this dylib was loaded by the bare name %s, so no "
            "sibling can be found beside it; set VRGLFIX_MESA_EGL",
            self.dli_fname);
    return NULL;
  }

  written = snprintf(path, sizeof path, "%.*s/../lib/libEGL.dylib",
                     (int)(lastSeparator - self.dli_fname), self.dli_fname);
  if (written < 0 || (size_t)written >= sizeof path) {
    logLine("FATAL no room for ../lib/libEGL.dylib beneath %s; set "
            "VRGLFIX_MESA_EGL",
            self.dli_fname);
    return NULL;
  }
  return path;
}

/* Guard clause: without eglGetProcAddress there is nowhere to forward to. */
static void resolveMesaEgl(void) {
  const char *override = getenv("VRGLFIX_MESA_EGL");
  const char *path = (override != NULL && override[0] != '\0')
                         ? override
                         : mesaEglPathBesideSelf();
  const char *error;

  /* mesaEglPathBesideSelf has already said why, and how to get past it. */
  if (path == NULL) return;

  mesaEglHandle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
  if (mesaEglHandle == NULL) {
    error = dlerror();
    logLine("FATAL could not dlopen Mesa EGL at %s: %s", path,
            error != NULL ? error : "(no dlerror)");
    return;
  }

  /*
   * Deliberately not dlsym(RTLD_DEFAULT, ...). This handle lookup asks
   * libEGL for eglGetProcAddress and nothing else, so it is unaffected by
   * libgl_interpose's dlsym hook and can never come back to us.
   */
  mesaEglGetProcAddress =
      (egl_get_proc_address_t)dlsym(mesaEglHandle, "eglGetProcAddress");
  if (mesaEglGetProcAddress == NULL) {
    error = dlerror();
    logLine("FATAL Mesa EGL has no eglGetProcAddress: %s",
            error != NULL ? error : "(no dlerror)");
    return;
  }
  logLine("Mesa EGL ready at %s, forwarding the shim's GL calls there", path);
}

/*
 * Resolve one GL entrypoint from Mesa. Deliberately never falls back to
 * dlsym(RTLD_DEFAULT) or a dlopen("libGL") handle: Apple's OpenGL would win
 * there, which is the bug being fixed.
 */
static void *resolveMesaEntryPoint(const char *glName) {
  void *entry;

  pthread_once(&mesaOnce, resolveMesaEgl);
  if (mesaEglGetProcAddress == NULL) return NULL;

  entry = mesaEglGetProcAddress(glName);
  if (entry == NULL) {
    logLine("FATAL Mesa does not implement %s; the shim's call cannot be saved",
            glName);
  }
  return entry;
}

/*
 * Log each entry point the first time it is reached. The flag is a local of the
 * replacement function itself, so there is exactly one per entry point and no
 * two names can collide. A racing second thread may log a duplicate, which is
 * harmless for a diagnostic line.
 */
#define VRGLFIX_NOTE_FIRST_CALL(glName)           \
  do {                                            \
    static bool alreadyLogged = false;            \
    if (!alreadyLogged) {                         \
      alreadyLogged = true;                       \
      logLine("intercepted %s -> Mesa", #glName); \
    }                                             \
  } while (0)

/* ------------------------------------------------------------------ */
/* The 25 GL entry points the shim imports                              */
/* ------------------------------------------------------------------ */

#define VRGLFIX_FORWARD_VOID(glName, params, args)                            \
  static __typeof__(&glName) real_##glName;                                  \
  void redirect_##glName params {                                             \
    if (real_##glName == NULL) {                                             \
      real_##glName = (__typeof__(&glName))resolveMesaEntryPoint(#glName);    \
    }                                                                        \
    if (real_##glName == NULL) return;                                       \
    VRGLFIX_NOTE_FIRST_CALL(glName);                                          \
    real_##glName args;                                                      \
  }                                                                           \
  DYLD_INTERPOSE(redirect_##glName, glName)

#define VRGLFIX_FORWARD_RET(ret, glName, params, args, onMissing)             \
  static __typeof__(&glName) real_##glName;                                  \
  ret redirect_##glName params {                                              \
    if (real_##glName == NULL) {                                             \
      real_##glName = (__typeof__(&glName))resolveMesaEntryPoint(#glName);    \
    }                                                                        \
    if (real_##glName == NULL) return onMissing;                             \
    VRGLFIX_NOTE_FIRST_CALL(glName);                                          \
    return real_##glName args;                                               \
  }                                                                           \
  DYLD_INTERPOSE(redirect_##glName, glName)

VRGLFIX_FORWARD_VOID(glBindBuffer, (GLenum target, GLuint buffer),
                     (target, buffer));
VRGLFIX_FORWARD_VOID(glBindFramebuffer, (GLenum target, GLuint framebuffer),
                     (target, framebuffer));
VRGLFIX_FORWARD_VOID(glBindTexture, (GLenum target, GLuint texture),
                     (target, texture));
VRGLFIX_FORWARD_VOID(glBlitFramebuffer,
                     (GLint srcX0, GLint srcY0, GLint srcX1, GLint srcY1,
                      GLint dstX0, GLint dstY0, GLint dstX1, GLint dstY1,
                      GLbitfield mask, GLenum filter),
                     (srcX0, srcY0, srcX1, srcY1, dstX0, dstY0, dstX1, dstY1,
                      mask, filter));
VRGLFIX_FORWARD_VOID(glBufferData,
                     (GLenum target, GLsizeiptr size, const GLvoid *data,
                      GLenum usage),
                     (target, size, data, usage));
VRGLFIX_FORWARD_RET(GLenum, glCheckFramebufferStatus, (GLenum target),
                    (target), (GLenum)0);
VRGLFIX_FORWARD_RET(GLenum, glClientWaitSync,
                    (GLsync sync, GLbitfield flags, GLuint64 timeout),
                    (sync, flags, timeout), (GLenum)0);
VRGLFIX_FORWARD_VOID(glDeleteFramebuffers,
                     (GLsizei n, const GLuint *framebuffers),
                     (n, framebuffers));
VRGLFIX_FORWARD_VOID(glDeleteSync, (GLsync sync), (sync));
VRGLFIX_FORWARD_VOID(glDeleteTextures, (GLsizei n, const GLuint *textures),
                     (n, textures));
VRGLFIX_FORWARD_VOID(glDisable, (GLenum cap), (cap));
VRGLFIX_FORWARD_VOID(glEnable, (GLenum cap), (cap));
VRGLFIX_FORWARD_RET(GLsync, glFenceSync, (GLenum condition, GLbitfield flags),
                    (condition, flags), NULL);
VRGLFIX_FORWARD_VOID(glFlush, (void), ());
VRGLFIX_FORWARD_VOID(glFramebufferTexture2D,
                     (GLenum target, GLenum attachment, GLenum textarget,
                      GLuint texture, GLint level),
                     (target, attachment, textarget, texture, level));
VRGLFIX_FORWARD_VOID(glGenBuffers, (GLsizei n, GLuint *buffers), (n, buffers));
VRGLFIX_FORWARD_VOID(glGenFramebuffers, (GLsizei n, GLuint *framebuffers),
                     (n, framebuffers));
VRGLFIX_FORWARD_VOID(glGenTextures, (GLsizei n, GLuint *textures),
                     (n, textures));
VRGLFIX_FORWARD_RET(GLenum, glGetError, (void), (), (GLenum)0);
VRGLFIX_FORWARD_VOID(glGetIntegerv, (GLenum pname, GLint *params),
                     (pname, params));
VRGLFIX_FORWARD_VOID(glGetTexImage,
                     (GLenum target, GLint level, GLenum format, GLenum type,
                      GLvoid *pixels),
                     (target, level, format, type, pixels));
VRGLFIX_FORWARD_VOID(glGetTexLevelParameteriv,
                     (GLenum target, GLint level, GLenum pname, GLint *params),
                     (target, level, pname, params));
VRGLFIX_FORWARD_RET(GLboolean, glIsEnabled, (GLenum cap), (cap), (GLboolean)0);
VRGLFIX_FORWARD_RET(GLvoid *, glMapBuffer, (GLenum target, GLenum access),
                    (target, access), NULL);
VRGLFIX_FORWARD_RET(GLboolean, glUnmapBuffer, (GLenum target), (target),
                    (GLboolean)0);

/* ------------------------------------------------------------------ */
/* Load-time report: proves the tuples are in the binary                */
/* ------------------------------------------------------------------ */

__attribute__((constructor)) static void vrglfixAnnounce(void) {
  logLine("loaded, 25 GL entry points interposed away from OpenGL.framework");
}