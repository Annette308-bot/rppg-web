import os
import tempfile
import time
import requests

from django.conf import settings
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect

API_URL = os.getenv("RPPG_API_URL", "https://rppg-server-pack.onrender.com/upload_video")


@csrf_protect
def video_upload_view(request):
    context = {}

    if request.method == "POST":
        temp_file_path = None

        try:
            video_file = request.FILES.get("video_file")
            if not video_file:
                context["error_message"] = "No video file was uploaded."
                return render(request, "web/video_upload.html", context)

            if not (video_file.content_type or "").startswith("video/"):
                context["error_message"] = "Invalid file type."
                return render(request, "web/video_upload.html", context)

            if video_file.size > 100 * 1024 * 1024:
                context["error_message"] = "File too large (max 100MB)."
                return render(request, "web/video_upload.html", context)

            # 1) Read metadata from the HTML form (POST)
            subject_id = (request.POST.get("subject_id", "S01") or "S01").strip()
            condition  = (request.POST.get("condition", "rest") or "rest").strip().lower()
            modality   = (request.POST.get("modality", "face") or "face").strip().lower()
            method     = (request.POST.get("method", "thesis_precomputed") or "thesis_precomputed").strip()

            # 2) Optional: auto-detect from filename
            name_lower = (video_file.name or "").lower()
            if "breath" in name_lower:
                condition = "breath"
            elif "exercise" in name_lower:
                condition = "exercise"
            elif "rest" in name_lower:
                condition = "rest"

            if "palm" in name_lower:
                modality = "palm"
            elif "face" in name_lower:
                modality = "face"

            # Save temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                for chunk in video_file.chunks():
                    tmp.write(chunk)
                temp_file_path = tmp.name

            # Call API
            with open(temp_file_path, "rb") as f:
                files = {"file": (video_file.name, f, video_file.content_type)}
                data = {
                    "subject_id": subject_id,
                    "condition": condition,
                    "modality": modality,
                    "method": method,
                    "min_valid_pct": 50,
                    "save": 0,          # keep 0 on web side (saving is handled on backend)
                    "timeout_sec": 180, # backend must support this
                }

                # Retry once for transient Render 502/503/504
                resp = requests.post(API_URL, files=files, data=data, timeout=200)
                if resp.status_code in (502, 503, 504):
                    time.sleep(1.2)
                    resp = requests.post(API_URL, files=files, data=data, timeout=200)

                resp.raise_for_status()
                rppg_result = resp.json()

            # Cleanup temp file
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

            # Disable preview on server (avoid huge base64 = “response ended prematurely”)
            video_data_url = None
            # If you ever want preview locally only:
            # if settings.DEBUG and video_file.size < 8 * 1024 * 1024:
            #     video_file.seek(0)
            #     video_data_url = "data:...base64,..."

            context.update({
                "video_data": {
                    "name": video_file.name,
                    "size": video_file.size,
                    "content_type": video_file.content_type,
                },
                "video_data_url": video_data_url,
                "p_result": rppg_result,
                "p_status": "completed",
                "success_msg": "Video uploaded and analyzed successfully!",
                # so the form keeps your choices
                "subject_id": subject_id,
                "condition": condition,
                "modality": modality,
                "method": method,
            })

        except Exception as e:
            context["error_message"] = f"API request failed: {e}"

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

    return render(request, "web/video_upload.html", context)
