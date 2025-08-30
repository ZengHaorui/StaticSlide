import os, json
from flask import Flask, request, render_template, send_file, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', template_folder='templates')

RESOURCE_DIR = os.path.join(os.path.dirname(__file__), "resource")
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.avi'}

def get_resource_pairs():
    files = os.listdir(RESOURCE_DIR)
    videos = [f for f in files if os.path.splitext(f)[1] in ALLOWED_VIDEO_EXTENSIONS]
    jsons = [f for f in files if f.endswith('.json')]
    pairs = []
    for v in videos:
        name = os.path.splitext(v)[0]
        jfile = name + ".json"
        if jfile in jsons:
            pairs.append({
                "name": name,
                "video": v,
                "json": jfile
            })
    return pairs

current_resource = {"video": None, "json": None, "clips_json": None}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/resource_list")
def resource_list():
    pairs = get_resource_pairs()
    return jsonify(pairs)

@app.route("/api/load_resource", methods=["POST"])
def load_resource():
    data = request.json
    video = data.get("video")
    jsonf = data.get("json")
    video_path = os.path.join(RESOURCE_DIR, secure_filename(video))
    json_path = os.path.join(RESOURCE_DIR, secure_filename(jsonf))
    if not (os.path.isfile(video_path) and os.path.isfile(json_path)):
        return jsonify({"error": "File not found"}), 404
    current_resource["video"] = video
    current_resource["json"] = jsonf
    with open(json_path, "r", encoding="utf-8") as f:
        current_resource["clips_json"] = json.load(f)
    return jsonify({"success": True})

@app.route("/api/video")
def serve_video():
    if not current_resource["video"]:
        return "", 404
    return send_from_directory(RESOURCE_DIR, current_resource["video"])

@app.route("/api/json")
def serve_json():
    if not current_resource["clips_json"]:
        return jsonify({})
    return jsonify(current_resource["clips_json"])

@app.route("/api/set_json", methods=["POST"])
def set_json():
    j = request.json
    current_resource["clips_json"] = j
    # 若已加载资源，则覆盖文件
    if current_resource["json"]:
        json_path = os.path.join(RESOURCE_DIR, current_resource["json"])
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(j, f, indent=2, ensure_ascii=False)
    return jsonify({"success": True})

if __name__ == "__main__":
    os.makedirs(RESOURCE_DIR, exist_ok=True)
    app.run(debug=True)