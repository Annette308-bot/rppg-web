from django.urls import path
from .views import video_upload_view

app_name = "web"
urlpatterns = [
    path("", video_upload_view, name="upload-video")
]