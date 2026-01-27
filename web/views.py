import os
import tempfile
import requests

from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect

API_URL = os.getenv("RPPG_API_URL", "https://rppg-server-pack.onrender.com/upload_video")
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100MB


@csrf_protect
def video_upload_view(request):
    context = {}

    if request.method == "POST":
        temp_file_path = None
        resp = None  # for debugging in exception

        try:
            video_file = request.FILES.get("video_file")

            if not video_file:
                context["error_message"] = "No video file was uploaded."
                return render(request, "web/video_upload.html", context)

            content_type = (video_file.content_type or "").lower()
            if not content_type.startswith("video/"):
                context["error_message"] = f"Invalid file type: {video_file.content_type}"
                return render(request, "web/video_upload.html", context)

            if video_file.size > MAX_VIDEO_BYTES:
                context["error_message"] = "File too large (max 100MB)."
                return render(request, "web/video_upload.html", context)

            # 1) Read metadata from the HTML form (POST)
            subject_id = (request.POST.get("subject_id", "S01") or "S01").strip()
            condition = (request.POST.get("condition", "rest") or "rest").strip().lower()
            modality = (request.POST.get("modality", "face") or "face").strip().lower()
            method = (request.POST.get("method", "thesis_precomputed") or "thesis_precomputed").strip()

            # 2) Optional: auto-detect from filename if user didn’t choose (or left defaults)
            name_lower = (video_file.name or "").lower()

            # If user left "rest", allow filename to override
            if condition in ("", "rest"):
                if "breath" in name_lower:
                    condition = "breath"
                elif "exercise" in name_lower:
                    condition = "exercise"
                elif "rest" in name_lower:
                    condition = "rest"

            # If user left "face", allow filename to override
            if modality in ("", "face"):
                if "palm" in name_lower:
                    modality = "palm"
                elif "face" in name_lower:
                    modality = "face"

            # Save temp file to disk (so we can send it to the API)
            ext = os.path.splitext(video_file.name)[1].lower() or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in video_file.chunks():
                    tmp.write(chunk)
                temp_file_path = tmp.name

            # 3) Call your API using the selected metadata
            with open(temp_file_path, "rb") as f:
                files = {
                    "file": (video_file.name, f, video_file.content_type or "video/mp4")
                }

                data = {
                    "subject_id": subject_id,
                    "condition": condition,
                    "modality": modality,
                    "method": method,
                    "min_valid_pct": 50,
                    "save": 0,
                    "timeout_sec": 120,
                }

                # Slightly longer timeout for cloud processing
                resp = requests.post(API_URL, files=files, data=data, timeout=180)
                resp.raise_for_status()
                rppg_result = resp.json()

            # Cleanup temp file
            os.unlink(temp_file_path)
            temp_file_path = None

            # IMPORTANT: do NOT embed the whole video in HTML (base64). It breaks on Render.
            context.update({
                "video_data": {
                    "name": video_file.name,
                    "size": video_file.size,
                    "content_type": video_file.content_type,
                    "subject_id": subject_id,
                    "condition": condition,
                    "modality": modality,
                    "method": method,
                },
                "video_data_url": None,  # preview disabled to keep server stable
                "p_result": rppg_result,
                "p_status": "completed",
                "success_msg": "Video uploaded and analyzed successfully!",
            })

        except requests.exceptions.RequestException as e:
            msg = f"API request failed: {e}"
            # include HTTP status/body if available
            try:
                if resp is not None:
                    msg += f" | status={resp.status_code} | body={resp.text[:500]}"
            except Exception:
                pass
            context["error_message"] = msg

        except Exception as e:
            context["error_message"] = str(e)

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    return render(request, "web/video_upload.html", context)
