\[EditScreen] 步骤2/3: 上传元数据到服务器...
EditScreen.tsx:329 \[EditScreen] 元数据上传完成: {duration: '0:11', id: 'mat\_1777090160570\_glktrjbsb', is\_local: true, message: '素材元数据已保存（客户端本地渲染）', originalName: 'local\_video.mp4', …}
EditScreen.tsx:330 \[EditScreen] ====== 客户端渲染上传成功 ======
21EditScreen.tsx:166 \[Polling] No processing materials to check
EditScreen.tsx:142 \[WebSocket] Closing connection
EditScreen.tsx:134 \[WebSocket] Disconnected
EditScreen.tsx:200 \[Polling] Stopping transcode status polling
ResultsScreen.tsx:130 \[ResultsScreen] 已缓存视频: 0 个
ResultsScreen.tsx:130 \[ResultsScreen] 已缓存视频: 0 个
EditScreen.tsx:100 WebSocket connection to 'ws\://localhost:3002/socket.io/?EIO=4\&transport=websocket' failed: Invalid frame header
doOpen @ socket\_\_io-client.js?v=b792a26f:1483
open @ socket\_\_io-client.js?v=b792a26f:953
open @ socket\_\_io-client.js?v=b792a26f:1841
\_Socket @ socket\_\_io-client.js?v=b792a26f:1792
open @ socket\_\_io-client.js?v=b792a26f:3576
Manager @ socket\_\_io-client.js?v=b792a26f:3511
lookup2 @ socket\_\_io-client.js?v=b792a26f:3830
$RefreshSig$ @ EditScreen.tsx:100
react\_stack\_bottom\_frame @ react-dom\_client.js?v=b792a26f:18567
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
commitHookEffectListMount @ react-dom\_client.js?v=b792a26f:9411
commitHookPassiveMountEffects @ react-dom\_client.js?v=b792a26f:9465
reconnectPassiveEffects @ react-dom\_client.js?v=b792a26f:11273
doubleInvokeEffectsOnFiber @ react-dom\_client.js?v=b792a26f:13339
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13312
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13317
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13317
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13317
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13317
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13317
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13317
recursivelyTraverseAndDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13317
commitDoubleInvokeEffectsInDEV @ react-dom\_client.js?v=b792a26f:13347
flushPassiveEffects @ react-dom\_client.js?v=b792a26f:13157
flushPendingEffects @ react-dom\_client.js?v=b792a26f:13088
flushSpawnedWork @ react-dom\_client.js?v=b792a26f:13062
commitRoot @ react-dom\_client.js?v=b792a26f:12804
commitRootWhenReady @ react-dom\_client.js?v=b792a26f:12016
performWorkOnRoot @ react-dom\_client.js?v=b792a26f:11950
performSyncWorkOnRoot @ react-dom\_client.js?v=b792a26f:13517
flushSyncWorkAcrossRoots\_impl @ react-dom\_client.js?v=b792a26f:13414
processRootScheduleInMicrotask @ react-dom\_client.js?v=b792a26f:13437
(anonymous) @ react-dom\_client.js?v=b792a26f:13531
ResultsScreen.tsx:130 \[ResultsScreen] 已缓存视频: 0 个
ResultsScreen.tsx:390 \[ResultsScreen] 播放处理，客户端渲染状态: 开启
ResultsScreen.tsx:324 \[ResultsScreen] ====== 尝试客户端渲染预览 ======
ResultsScreen.tsx:325 \[ResultsScreen] 组合ID: combo\_ec618317-1ae3-42c3-97d5-4123f85bd93b\_0 素材数: 2
ResultsScreen.tsx:334 \[ResultsScreen] 从本地存储加载素材...
ResultsScreen.tsx:336 \[ResultsScreen] 本地素材加载结果: 2 / 2 个
ResultsScreen.tsx:344 \[ResultsScreen] 开始客户端秒级拼接...
ResultsScreen.tsx:349 \[ResultsScreen] 拼接进度: 0% - preparing
ResultsScreen.tsx:349 \[ResultsScreen] 拼接进度: 30% - concatenating
ResultsScreen.tsx:349 \[ResultsScreen] 拼接进度: 36% - concatenating
ffmpeg.ts:51 \[FFmpeg] ffmpeg version 5.1.4 Copyright (c) 2000-2023 the FFmpeg developers
ffmpeg.ts:51 \[FFmpeg] built with emcc (Emscripten gcc/clang-like replacement + linker emulating GNU ld) 3.1.40 (5c27e79dd0a9c4e27ef2326841698cdd4f6b5784)
ffmpeg.ts:51 \[FFmpeg] configuration: --target-os=none --arch=x86\_32 --enable-cross-compile --disable-asm --disable-stripping --disable-programs --disable-doc --disable-debug --disable-runtime-cpudetect --disable-autodetect --nm=emnm --ar=emar --ranlib=emranlib --cc=emcc --cxx=em++ --objcc=emcc --dep-cc=emcc --extra-cflags='-I/opt/include -O3 -msimd128' --extra-cxxflags='-I/opt/include -O3 -msimd128' --disable-pthreads --disable-w32threads --disable-os2threads --enable-gpl --enable-libx264 --enable-libx265 --enable-libvpx --enable-libmp3lame --enable-libtheora --enable-libvorbis --enable-libopus --enable-zlib --enable-libwebp --enable-libfreetype --enable-libfribidi --enable-libass --enable-libzimg
ffmpeg.ts:51 \[FFmpeg] libavutil 57. 28.100 / 57. 28.100
ffmpeg.ts:51 \[FFmpeg] libavcodec 59. 37.100 / 59. 37.100
ffmpeg.ts:51 \[FFmpeg] libavformat 59. 27.100 / 59. 27.100
ffmpeg.ts:51 \[FFmpeg] libavdevice 59. 7.100 / 59. 7.100
ffmpeg.ts:51 \[FFmpeg] libavfilter 8. 44.100 / 8. 44.100
ffmpeg.ts:51 \[FFmpeg] libswscale 6. 7.100 / 6. 7.100
ffmpeg.ts:51 \[FFmpeg] libswresample 4. 7.100 / 4. 7.100
ffmpeg.ts:51 \[FFmpeg] libpostproc 56. 6.100 / 56. 6.100
ffmpeg.ts:51 \[FFmpeg] \[mov,mp4,m4a,3gp,3g2,mj2 @ 0xdeb330] Auto-inserting h264\_mp4toannexb bitstream filter
ffmpeg.ts:51 \[FFmpeg] Input #0, concat, from 'list\_1777090187305.txt':
ffmpeg.ts:51 \[FFmpeg] Duration: N/A, start: 0.000000, bitrate: 2275 kb/s
ffmpeg.ts:51 \[FFmpeg] Stream #0:0(und): Video: h264 (Constrained Baseline) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1080x1920 \[SAR 1:1 DAR 9:16], 2149 kb/s, 29.92 fps, 30 tbr, 30k tbn
ffmpeg.ts:51 \[FFmpeg] Metadata:
ffmpeg.ts:51 \[FFmpeg] handler\_name : VideoHandler
ffmpeg.ts:51 \[FFmpeg] vendor\_id : \[0]\[0]\[0]\[0]
ffmpeg.ts:51 \[FFmpeg] encoder : AVC1 Coding
ffmpeg.ts:51 \[FFmpeg] Stream #0:1(und): Audio: opus (Opus / 0x7375704F), 48000 Hz, stereo, fltp, 126 kb/s
ffmpeg.ts:51 \[FFmpeg] Metadata:
ffmpeg.ts:51 \[FFmpeg] handler\_name : SoundHandler
ffmpeg.ts:51 \[FFmpeg] vendor\_id : \[0]\[0]\[0]\[0]
ffmpeg.ts:51 \[FFmpeg] \[mp4 @ 0xef9220] track 1: codec frame size is not set
ffmpeg.ts:51 \[FFmpeg] Output #0, mp4, to 'concat\_1777090187305.mp4':
ffmpeg.ts:51 \[FFmpeg] Metadata:
ffmpeg.ts:51 \[FFmpeg] encoder : Lavf59.27.100
ffmpeg.ts:51 \[FFmpeg] Stream #0:0(und): Video: h264 (Constrained Baseline) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1080x1920 \[SAR 1:1 DAR 9:16], q=2-31, 2149 kb/s, 29.92 fps, 30 tbr, 30k tbn
ffmpeg.ts:51 \[FFmpeg] Metadata:
ffmpeg.ts:51 \[FFmpeg] handler\_name : VideoHandler
ffmpeg.ts:51 \[FFmpeg] vendor\_id : \[0]\[0]\[0]\[0]
ffmpeg.ts:51 \[FFmpeg] encoder : AVC1 Coding
ffmpeg.ts:51 \[FFmpeg] Stream #0:1(und): Audio: opus (Opus / 0x7375704F), 48000 Hz, stereo, fltp, 126 kb/s
ffmpeg.ts:51 \[FFmpeg] Metadata:
ffmpeg.ts:51 \[FFmpeg] handler\_name : SoundHandler
ffmpeg.ts:51 \[FFmpeg] vendor\_id : \[0]\[0]\[0]\[0]
ffmpeg.ts:51 \[FFmpeg] Stream mapping:
ffmpeg.ts:51 \[FFmpeg] Stream #0:0 -> #0:0 (copy)
ffmpeg.ts:51 \[FFmpeg] Stream #0:1 -> #0:1 (copy)
ffmpeg.ts:57 \[FFmpeg] Progress: -3300%
ffmpeg.ts:51 \[FFmpeg] frame= 1 fps=0.0 q=-1.0 size= 0kB time=00:00:00.00 bitrate=11636.4kbits/s speed=N/A\
ffmpeg.ts:51 \[FFmpeg] \[mov,mp4,m4a,3gp,3g2,mj2 @ 0xdf27f0] Auto-inserting h264\_mp4toannexb bitstream filter
ffmpeg.ts:51 \[FFmpeg] \[mp4 @ 0xef9220] Starting second pass: moving the moov atom to the beginning of the file
ffmpeg.ts:57 \[FFmpeg] Progress: -2193326700%
ffmpeg.ts:51 \[FFmpeg] frame= 657 fps=0.0 q=-1.0 Lsize= 5964kB time=00:00:21.93 bitrate=2227.7kbits/s speed= 141x\
ffmpeg.ts:57 \[FFmpeg] Progress: 100%
ffmpeg.ts:51 \[FFmpeg] video:5609kB audio:337kB subtitle:0kB other streams:0kB global headers:0kB muxing overhead: 0.309656%
ffmpeg.ts:51 \[FFmpeg] Aborted()
ResultsScreen.tsx:349 \[ResultsScreen] 拼接进度: 78% - concatenating
ResultsScreen.tsx:349 \[ResultsScreen] 拼接进度: 90% - concatenating
ResultsScreen.tsx:349 \[ResultsScreen] 拼接进度: 90% - saving
opfs.ts:157 \[OPFS] Render saved: result\_combo\_ec618317-1ae3-42c3-97d5-4123f85bd93b\_0
ResultsScreen.tsx:349 \[ResultsScreen] 拼接进度: 100% - completed
ResultsScreen.tsx:353 \[ResultsScreen] 客户端拼接完成，耗时: 407 ms
ResultsScreen.tsx:357 \[ResultsScreen] ====== 客户端渲染预览成功 ======
ResultsScreen.tsx:144 \[缓存] 视频已在本地: combo\_ec618317-1ae3-42c3-97d5-4123f85bd93b\_0
OptimizedVideoPlayer.tsx:52 \[OptimizedVideoPlayer] 使用本地缓存播放: combo\_ec618317-1ae3-42c3-97d5-4123f85bd93b\_0
