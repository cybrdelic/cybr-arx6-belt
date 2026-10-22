"""Native platform GL context; WebGL2 viewer is the macOS SSBO fallback."""
import os
import sys

def create_context(version):
    import glcontext
    backend = os.environ.get("ARX_GL_BACKEND", "auto").lower()
    if backend not in ("auto", "native", "egl"):
        raise ValueError("ARX_GL_BACKEND must be auto, native or egl")
    if sys.platform == "darwin" and version > 410:
        raise RuntimeError("The native numeric-table renderer needs OpenGL 4.3 SSBOs. macOS supports the WebGL2 UBO viewer instead: python tools/portable.py viewer-build")
    choices = ["egl", "native"] if backend == "auto" and sys.platform.startswith("linux") else ["native" if backend == "auto" else backend]
    errors = []
    for name in choices:
        context = None
        try:
            factory = glcontext.get_backend_by_name("egl") if name == "egl" else glcontext.default_backend()
            context = factory(glversion=version, mode="standalone")
            context.__enter__()
            return context, name
        except Exception as exc:
            if context is not None:
                context.release()
            errors.append(name + ": " + str(exc))
    raise RuntimeError("No supported OpenGL context: " + "; ".join(errors) + ". Try the WebGL2 viewer; a desktop GPU driver or Mesa is required.")
