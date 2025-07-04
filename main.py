from flask import Flask, request, send_file
import os
import subprocess
import uuid

UPLOAD_DIR = "/tmp"
OUTPUT_WIDTH = 720
OUTPUT_HEIGHT = 1280

app = Flask(__name__)

@app.route('/edit', methods=['POST'])
def edit_video():
    if 'file' not in request.files:
        return {'error': 'Missing file'}, 400

    file = request.files['file']

    raw_filename = f"raw_{uuid.uuid4()}.mp4"
    cropped_filename = f"cropped_{uuid.uuid4()}.mp4"
    edited_filename = f"edited_{uuid.uuid4()}.mp4"
    raw_path = os.path.join(UPLOAD_DIR, raw_filename)
    cropped_path = os.path.join(UPLOAD_DIR, cropped_filename)
    edited_path = os.path.join(UPLOAD_DIR, edited_filename)

    file.save(raw_path)

    try:
        # Step 1: Detect crop area
        cropdetect_cmd = [
            "ffmpeg", "-i", raw_path,
            "-t", "2", "-vf", "cropdetect=24:16:0",
            "-f", "null", "-"
        ]
        result = subprocess.run(cropdetect_cmd, capture_output=True, text=True)

        # Extract crop parameters from log
        crop_lines = [line for line in result.stderr.split('\n') if "crop=" in line]
        crop_values = [line.split("crop=")[-1].strip() for line in crop_lines if "crop=" in line]
        crop_filter = crop_values[-1] if crop_values else None

        if not crop_filter:
            crop_filter = "in_w:in_h:0:0"  # fallback to original size

        # Step 2: Crop the video to content area
        crop_cmd = [
            "ffmpeg", "-i", raw_path,
            "-vf", f"crop={crop_filter}",
            "-c:a", "copy", "-y", cropped_path
        ]
        subprocess.run(crop_cmd, check=True)

        # Step 3: Resize and pad to 720x1280 (portrait)
        scale_and_pad = (
            f"scale=w={OUTPUT_WIDTH}:h=-1:force_original_aspect_ratio=decrease," 
            f"pad={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:white"
        )

        final_cmd = [
            "ffmpeg", "-i", cropped_path,
            "-vf", scale_and_pad,
            "-c:a", "copy",
            "-preset", "ultrafast",
            "-y", edited_path
        ]
        subprocess.run(final_cmd, check=True)

        return send_file(edited_path, mimetype='video/mp4')

    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        for path in [raw_path, cropped_path, edited_path]:
            if os.path.exists(path):
                os.remove(path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
