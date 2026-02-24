from fastapi.templating import Jinja2Templates

# Initialize once here to be shared across all route files
templates = Jinja2Templates(directory="templates")