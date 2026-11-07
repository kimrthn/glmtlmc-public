# SDL3

`stack/lib/libSDL3.dylib` is an altered build of SDL 3.4.14
(https://github.com/libsdl-org/SDL, tag `release-3.4.14`), not the original.
It keeps desktop OpenGL on EGL when `SDL_VIDEO_FORCE_EGL` is set. The full change:

```diff
--- a/src/video/cocoa/SDL_cocoaopengles.m
+++ b/src/video/cocoa/SDL_cocoaopengles.m
@@ -26,12 +26,14 @@
 #include "SDL_cocoaopengles.h"
 #include "SDL_cocoaopengl.h"
 
+#import <QuartzCore/CAMetalLayer.h>
+
 // EGL implementation of SDL OpenGL support
 
 bool Cocoa_GLES_LoadLibrary(SDL_VideoDevice *_this, const char *path)
 {
     // If the profile requested is not GL ES, switch over to WIN_GL functions
-    if (_this->gl_config.profile_mask != SDL_GL_CONTEXT_PROFILE_ES) {
+    if (_this->gl_config.profile_mask != SDL_GL_CONTEXT_PROFILE_ES && !SDL_GetHintBoolean(SDL_HINT_VIDEO_FORCE_EGL, false)) {
 #ifdef SDL_VIDEO_OPENGL_CGL
         Cocoa_GLES_UnloadLibrary(_this);
         _this->GL_LoadLibrary = Cocoa_GL_LoadLibrary;
@@ -64,7 +66,7 @@
         SDL_CocoaWindowData *data = (__bridge SDL_CocoaWindowData *)window->internal;
 
 #ifdef SDL_VIDEO_OPENGL_CGL
-        if (_this->gl_config.profile_mask != SDL_GL_CONTEXT_PROFILE_ES) {
+        if (_this->gl_config.profile_mask != SDL_GL_CONTEXT_PROFILE_ES && !SDL_GetHintBoolean(SDL_HINT_VIDEO_FORCE_EGL, false)) {
             // Switch to CGL based functions
             Cocoa_GLES_UnloadLibrary(_this);
             _this->GL_LoadLibrary = Cocoa_GL_LoadLibrary;
@@ -142,6 +144,14 @@
             return SDL_SetError("Could not create GLES window surface");
         }
 
+        // glmtlmc: Mesa sizes its layer for Retina; shrink it if the window asked for low density.
+        if (SDL_GetHintBoolean(SDL_HINT_VIDEO_FORCE_EGL, false) && !(window->flags & SDL_WINDOW_HIGH_PIXEL_DENSITY) &&
+            [v.layer isKindOfClass:[CAMetalLayer class]]) {
+            CAMetalLayer *layer = (CAMetalLayer *)v.layer;
+            layer.contentsScale = 1;
+            layer.drawableSize = v.bounds.size;
+        }
+
         return Cocoa_GLES_MakeCurrent(_this, current_win, current_ctx);
     }
 }
--- a/src/video/cocoa/SDL_cocoawindow.m
+++ b/src/video/cocoa/SDL_cocoawindow.m
@@ -523,7 +523,8 @@
 
     NSOpenGLContext *currentContext;
     NSMutableArray *contexts;
-    if (!data || !data.nscontexts) {
+    // glmtlmc: skip when no CGL context exists; OpenGL.framework is unusable with Mesa's libGL on the search path.
+    if (!data || data.nscontexts.count == 0) {
         return;
     }
 
@@ -1386,7 +1387,7 @@
     if ([oldscale doubleValue] != [_data.nswindow backingScaleFactor]) {
         // Update the content scale on the window layer
         // This is required to keep content scale in sync with ANGLE
-        contentView.layer.contentsScale = [_data.nswindow backingScaleFactor];
+        contentView.layer.contentsScale = (_data.window->flags & SDL_WINDOW_HIGH_PIXEL_DENSITY) ? [_data.nswindow backingScaleFactor] : 1;
         // Send a resize event when the backing scale factor changes.
         [self windowDidResize:aNotification];
     }
@@ -2539,7 +2540,7 @@
 #ifdef SDL_VIDEO_OPENGL_ES2
 #ifdef SDL_VIDEO_OPENGL_EGL
         if ((window->flags & SDL_WINDOW_OPENGL) &&
-            _this->gl_config.profile_mask == SDL_GL_CONTEXT_PROFILE_ES) {
+            (_this->gl_config.profile_mask == SDL_GL_CONTEXT_PROFILE_ES || SDL_GetHintBoolean(SDL_HINT_VIDEO_FORCE_EGL, false))) {
             [nsview setWantsLayer:TRUE];
             if ((window->flags & SDL_WINDOW_HIGH_PIXEL_DENSITY)) {
                 nsview.layer.contentsScale = nswindow.screen.backingScaleFactor;
@@ -2561,7 +2562,7 @@
 
         // The rest of this macro mess is for OpenGL or OpenGL ES windows
 #ifdef SDL_VIDEO_OPENGL_ES2
-        if (_this->gl_config.profile_mask == SDL_GL_CONTEXT_PROFILE_ES) {
+        if (_this->gl_config.profile_mask == SDL_GL_CONTEXT_PROFILE_ES || SDL_GetHintBoolean(SDL_HINT_VIDEO_FORCE_EGL, false)) {
 #ifdef SDL_VIDEO_OPENGL_EGL
             if (!Cocoa_GLES_SetupWindow(_this, window)) {
                 Cocoa_DestroyWindow(_this, window);
```
