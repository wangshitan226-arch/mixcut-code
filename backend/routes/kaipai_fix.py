@kaipai_bp.route('/kaipai/<edit_id>/render', methods=['POST'])
def start_render(edit_id):
    """启动视频渲染（裁剪）"""
    edit = KaipaiEdit.query.get(edit_id)
    if not edit:
        return jsonify({'error': 'Edit not found'}), 404
    
    # 获取编辑参数
    edit_params = json.loads(edit.edit_params) if edit.edit_params else {}
    removed_segments = edit_params.get('removed_segments', [])
    
    if not removed_segments:
        return jsonify({'error': '没有要删除的片段'}), 400
    
    # 获取所有需要在异步线程中使用的数据（避免session问题）
    video_url = edit.original_video_url
    user_id = edit.user_id
    asr_result = json.loads(edit.asr_result) if edit.asr_result else {}
    
    # 启动异步渲染任务
    task_id = str(uuid.uuid4())
    render_tasks[task_id] = {
        'status': 'processing',
        'progress': 0,
        'output_url': None,
        'error': None
    }
    
    # 获取当前应用实例（用于创建应用上下文）
    from flask import current_app
    app = current_app._get_current_object()
    
    # 异步执行视频裁剪
    def render_video():
        with app.app_context():
            try:
                render_tasks[task_id]['progress'] = 10
                
                # 计算保留的时间段（反向思考：删除selected的segments）
                all_segments = asr_result.get('sentences', [])
                
                # 获取要删除的时间段
                removed_times = [(s['beginTime'], s['endTime']) for s in removed_segments]
                
                # 计算保留的时间段
                keep_segments = []
                video_duration = asr_result.get('videoInfo', {}).get('duration', 0) * 1000
                
                current_time = 0
                for seg in all_segments:
                    seg_start = seg['beginTime']
                    seg_end = seg['endTime']
                    
                    # 检查这个片段是否被选中删除
                    is_removed = any(r[0] <= seg_start and r[1] >= seg_end for r in removed_times)
                    
                    if not is_removed:
                        keep_segments.append((seg_start, seg_end))
                
                render_tasks[task_id]['progress'] = 30
                
                # 使用ffmpeg裁剪视频
                output_filename = f"kaipai_render_{edit_id}_{int(datetime.now().timestamp())}.mp4"
                output_path = os.path.join('renders', output_filename)
                
                # 构建ffmpeg命令 - 使用复杂滤镜拼接多个时间段
                if len(keep_segments) == 0:
                    raise Exception('没有可保留的视频片段')
                
                # 下载原始视频到本地
                local_video_path = os.path.join('uploads', f'temp_{edit_id}.mp4')
                if video_url.startswith('http'):
                    import requests
                    response = requests.get(video_url)
                    with open(local_video_path, 'wb') as f:
                        f.write(response.content)
                else:
                    local_video_path = video_url.lstrip('/')
                
                render_tasks[task_id]['progress'] = 50
                
                # 构建ffmpeg filter_complex
                filter_parts = []
                concat_parts = []
                
                for i, (start, end) in enumerate(keep_segments):
                    start_sec = start / 1000
                    duration = (end - start) / 1000
                    filter_parts.append(f"[0:v]trim=start={start_sec}:duration={duration},setpts=PTS-STARTPTS[v{i}];")
                    filter_parts.append(f"[0:a]atrim=start={start_sec}:duration={duration},asetpts=PTS-STARTPTS[a{i}];")
                    concat_parts.append(f"[v{i}][a{i}]")
                
                filter_complex = ''.join(filter_parts) + ''.join(concat_parts) + f"concat=n={len(keep_segments)}:v=1:a=1[outv][outa]"
                
                cmd = [
                    'ffmpeg', '-y', '-i', local_video_path,
                    '-filter_complex', filter_complex,
                    '-map', '[outv]', '-map', '[outa]',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k',
                    output_path
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                render_tasks[task_id]['progress'] = 80
                
                # 上传到OSS
                oss_url = oss_client.upload_render(output_path, edit_id, user_id)
                
                render_tasks[task_id]['progress'] = 100
                render_tasks[task_id]['status'] = 'completed'
                render_tasks[task_id]['output_url'] = oss_url
                
                # 更新数据库（在新session中）
                from extensions import db
                from models import KaipaiEdit
                with db.session.begin():
                    edit_update = KaipaiEdit.query.get(edit_id)
                    if edit_update:
                        edit_update.output_video_url = oss_url
                        edit_update.status = 'completed'
                
                # 清理临时文件
                if os.path.exists(local_video_path) and 'temp_' in local_video_path:
                    os.remove(local_video_path)
                
            except Exception as e:
                render_tasks[task_id]['status'] = 'failed'
                render_tasks[task_id]['error'] = str(e)
                # 更新数据库状态为失败
                from extensions import db
                from models import KaipaiEdit
                with db.session.begin():
                    edit_update = KaipaiEdit.query.get(edit_id)
                    if edit_update:
                        edit_update.status = 'failed'
    
    thread = threading.Thread(target=render_video)
    thread.daemon = True
    thread.start()
    
    edit.status = 'processing'
    db.session.commit()
    
    return jsonify({
        'edit_id': edit_id,
        'status': 'processing',
        'task_id': task_id
    })
