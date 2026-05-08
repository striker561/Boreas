from app.core import app
from app.features.routes import feature_router

app.include_router(feature_router)
