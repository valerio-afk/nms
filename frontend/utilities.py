from . import frontend as bp, NMSBACKEND as BACKEND
from flask import jsonify, request, Response, flash, redirect, url_for

@bp.route('/check_tasks', methods=['POST'])
def check_tasks():
    data = request.get_json()

    if not data or 'path' not in data:
        return jsonify({"error": "Missing 'path' parameter"}), 400

    path = data['path']

    tasks = BACKEND.get_tasks_by_path(path)

    return jsonify([t.task_id for t in tasks])

@bp.route('/check_tasks/<string:task_id>', methods=['POST'])
def check_task_by_id(task_id:str) -> Response:
    task = BACKEND.get_task_by_id(task_id)

    if task is None:
        return jsonify({"progress": 100})

    return jsonify({
        "running": task.running,
        "progress": task.progress,
        "eta": task.eta,
        "message": str(task)
    })


@bp.route("/reboot", methods=['POST'])
def reboot():

    try:
        BACKEND.restart()
    except Exception as e:
        flash(str(e),"error")

    return redirect(url_for('main.dashboard'))


@bp.route("/shutdown", methods=['POST'])
def shutdown():
    BACKEND.shutdown()

    return redirect(url_for('main.dashboard'))