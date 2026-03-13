from fastapi import Request
from fastapi.templating import Jinja2Templates

# Initialize once here to be shared across all route files
templates = Jinja2Templates(directory="templates")

def render_template(template_name: str, request: Request, context: dict = {}):
    """Base template renderer that automatically injects current_user from request state."""
    full_context = {
        "request": request,
        "current_user": getattr(request.state, "user", None),
        **context
    }
    return templates.TemplateResponse(template_name, full_context)