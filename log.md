\[EditScreen] ====== 双轨并行上传成功 ======
EditScreen.tsx:166 \[Polling] No processing materials to check
EditScreen.tsx:207 \[Immediate Check] Starting for material e82a8a71-1630-4279-bc0d-8a4521a4aa81, task transcode\_e82a8a71-1630-4279-bc0d-8a4521a4aa81
EditScreen.tsx:166 \[Polling] No processing materials to check
EditScreen.tsx:214 \[Immediate Check] Status for e82a8a71-1630-4279-bc0d-8a4521a4aa81: completed
EditScreen.tsx:217 \[Immediate Check] Material e82a8a71-1630-4279-bc0d-8a4521a4aa81 completed!
14EditScreen.tsx:166 \[Polling] No processing materials to check
EditScreen.tsx:142 \[WebSocket] Closing connection
EditScreen.tsx:134 \[WebSocket] Disconnected
EditScreen.tsx:200 \[Polling] Stopping transcode status polling
useClientRendering.ts:62 \[ClientRendering] 客户端渲染已强制开启，跳过设备检测
ResultsScreen.tsx:145 \[ResultsScreen] 已缓存视频: 0 个
useClientRendering.ts:62 \[ClientRendering] 客户端渲染已强制开启，跳过设备检测
ResultsScreen.tsx:145 \[ResultsScreen] 已缓存视频: 0 个
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
ResultsScreen.tsx:145 \[ResultsScreen] 已缓存视频: 0 个
ResultsScreen.tsx:451 \[双轨制] ========== 点击预览，双轨并行开始 ==========
ResultsScreen.tsx:452 \[双轨制] 组合ID: combo\_cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34\_0
ResultsScreen.tsx:453 \[双轨制] 素材列表: 8e9983c7-6a84-405b-80bb-caace0d85069, e82a8a71-1630-4279-bc0d-8a4521a4aa81
ResultsScreen.tsx:456 \[双轨制] 🎬 轨道①: 启动服务器FFmpeg拼接+OSS上传（异步）
ResultsScreen.tsx:383 \[双轨制] ========== 服务器FFmpeg拼接+OSS上传开始 ==========
ResultsScreen.tsx:384 \[双轨制] 组合ID: combo\_cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34\_0
ResultsScreen.tsx:385 \[双轨制] 当前状态: server\_video\_url=无
ResultsScreen.tsx:388 \[双轨制] 调用接口: POST /api/combinations/combo\_cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34\_0/server-render
ResultsScreen.tsx:460 \[双轨制] 🌐 轨道②: 启动浏览器WebCodecs拼接
ResultsScreen.tsx:462 \[双轨制] 浏览器WebCodecs状态: ✅ 开启
ResultsScreen.tsx:465 \[双轨制] 调用 clientRenderPreview\...
ResultsScreen.tsx:339 \[ResultsScreen] ====== 尝试客户端渲染预览 ======
ResultsScreen.tsx:340 \[ResultsScreen] 组合ID: combo\_cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34\_0 素材数: 2
ResultsScreen.tsx:350 \[ResultsScreen] 从本地存储加载素材...
ResultsScreen.tsx:352 \[ResultsScreen] 本地素材加载结果: 0 / 2 个
ResultsScreen.tsx:355 \[ResultsScreen] 没有本地素材，降级到服务器渲染
$RefreshSig$ @ ResultsScreen.tsx:355
await in $RefreshSig$
$RefreshSig$ @ ResultsScreen.tsx:466
$RefreshSig$ @ ResultsScreen.tsx:1037
executeDispatch @ react-dom\_client.js?v=b792a26f:13622
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
processDispatchQueue @ react-dom\_client.js?v=b792a26f:13658
(anonymous) @ react-dom\_client.js?v=b792a26f:14071
batchedUpdates$1 @ react-dom\_client.js?v=b792a26f:2626
dispatchEventForPluginEventSystem @ react-dom\_client.js?v=b792a26f:13763
dispatchEvent @ react-dom\_client.js?v=b792a26f:16784
dispatchDiscreteEvent @ react-dom\_client.js?v=b792a26f:16765 <button>
exports.jsxDEV @ react\_jsx-dev-runtime.js?v=b792a26f:247
$RefreshSig$ @ ResultsScreen.tsx:1036
$RefreshSig$ @ ResultsScreen.tsx:989
react\_stack\_bottom\_frame @ react-dom\_client.js?v=b792a26f:18509
renderWithHooksAgain @ react-dom\_client.js?v=b792a26f:5729
renderWithHooks @ react-dom\_client.js?v=b792a26f:5665
updateFunctionComponent @ react-dom\_client.js?v=b792a26f:7475
beginWork @ react-dom\_client.js?v=b792a26f:8525
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
performUnitOfWork @ react-dom\_client.js?v=b792a26f:12561
workLoopSync @ react-dom\_client.js?v=b792a26f:12424
renderRootSync @ react-dom\_client.js?v=b792a26f:12408
performWorkOnRoot @ react-dom\_client.js?v=b792a26f:11766
performWorkOnRootViaSchedulerTask @ react-dom\_client.js?v=b792a26f:13505
performWorkUntilDeadline @ react-dom\_client.js?v=b792a26f:36 <ResultsScreen>
exports.jsxDEV @ react\_jsx-dev-runtime.js?v=b792a26f:247
AppContent @ App.tsx:306
react\_stack\_bottom\_frame @ react-dom\_client.js?v=b792a26f:18509
renderWithHooksAgain @ react-dom\_client.js?v=b792a26f:5729
renderWithHooks @ react-dom\_client.js?v=b792a26f:5665
updateFunctionComponent @ react-dom\_client.js?v=b792a26f:7475
beginWork @ react-dom\_client.js?v=b792a26f:8525
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
performUnitOfWork @ react-dom\_client.js?v=b792a26f:12561
workLoopSync @ react-dom\_client.js?v=b792a26f:12424
renderRootSync @ react-dom\_client.js?v=b792a26f:12408
performWorkOnRoot @ react-dom\_client.js?v=b792a26f:11766
performWorkOnRootViaSchedulerTask @ react-dom\_client.js?v=b792a26f:13505
performWorkUntilDeadline @ react-dom\_client.js?v=b792a26f:36
ResultsScreen.tsx:467 \[双轨制] clientRenderPreview 返回: ❌ 失败
ResultsScreen.tsx:477 \[双轨制] ⚠️ 轨道②失败，降级到本地FFmpeg拼接...
ResultsScreen.tsx:390 POST <http://localhost:3002/api/combinations/combo_cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34_0/server-render> 500 (INTERNAL SERVER ERROR)
$RefreshSig$ @ ResultsScreen.tsx:390
$RefreshSig$ @ ResultsScreen.tsx:457
$RefreshSig$ @ ResultsScreen.tsx:1037
executeDispatch @ react-dom\_client.js?v=b792a26f:13622
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
processDispatchQueue @ react-dom\_client.js?v=b792a26f:13658
(anonymous) @ react-dom\_client.js?v=b792a26f:14071
batchedUpdates$1 @ react-dom\_client.js?v=b792a26f:2626
dispatchEventForPluginEventSystem @ react-dom\_client.js?v=b792a26f:13763
dispatchEvent @ react-dom\_client.js?v=b792a26f:16784
dispatchDiscreteEvent @ react-dom\_client.js?v=b792a26f:16765 <button>
exports.jsxDEV @ react\_jsx-dev-runtime.js?v=b792a26f:247
$RefreshSig$ @ ResultsScreen.tsx:1036
$RefreshSig$ @ ResultsScreen.tsx:989
react\_stack\_bottom\_frame @ react-dom\_client.js?v=b792a26f:18509
renderWithHooksAgain @ react-dom\_client.js?v=b792a26f:5729
renderWithHooks @ react-dom\_client.js?v=b792a26f:5665
updateFunctionComponent @ react-dom\_client.js?v=b792a26f:7475
beginWork @ react-dom\_client.js?v=b792a26f:8525
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
performUnitOfWork @ react-dom\_client.js?v=b792a26f:12561
workLoopSync @ react-dom\_client.js?v=b792a26f:12424
renderRootSync @ react-dom\_client.js?v=b792a26f:12408
performWorkOnRoot @ react-dom\_client.js?v=b792a26f:11766
performWorkOnRootViaSchedulerTask @ react-dom\_client.js?v=b792a26f:13505
performWorkUntilDeadline @ react-dom\_client.js?v=b792a26f:36 <ResultsScreen>
exports.jsxDEV @ react\_jsx-dev-runtime.js?v=b792a26f:247
AppContent @ App.tsx:306
react\_stack\_bottom\_frame @ react-dom\_client.js?v=b792a26f:18509
renderWithHooksAgain @ react-dom\_client.js?v=b792a26f:5729
renderWithHooks @ react-dom\_client.js?v=b792a26f:5665
updateFunctionComponent @ react-dom\_client.js?v=b792a26f:7475
beginWork @ react-dom\_client.js?v=b792a26f:8525
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
performUnitOfWork @ react-dom\_client.js?v=b792a26f:12561
workLoopSync @ react-dom\_client.js?v=b792a26f:12424
renderRootSync @ react-dom\_client.js?v=b792a26f:12408
performWorkOnRoot @ react-dom\_client.js?v=b792a26f:11766
performWorkOnRootViaSchedulerTask @ react-dom\_client.js?v=b792a26f:13505
performWorkUntilDeadline @ react-dom\_client.js?v=b792a26f:36
ResultsScreen.tsx:395 \[双轨制] 后端响应状态码: 500
ResultsScreen.tsx:398 \[双轨制] 后端响应数据: {
"error": "name 'subprocess' is not defined"
}
ResultsScreen.tsx:411 \[双轨制] ❌ 服务器FFmpeg拼接+OSS上传失败: name 'subprocess' is not defined
$RefreshSig$ @ ResultsScreen.tsx:411
await in $RefreshSig$
$RefreshSig$ @ ResultsScreen.tsx:457
$RefreshSig$ @ ResultsScreen.tsx:1037
executeDispatch @ react-dom\_client.js?v=b792a26f:13622
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
processDispatchQueue @ react-dom\_client.js?v=b792a26f:13658
(anonymous) @ react-dom\_client.js?v=b792a26f:14071
batchedUpdates$1 @ react-dom\_client.js?v=b792a26f:2626
dispatchEventForPluginEventSystem @ react-dom\_client.js?v=b792a26f:13763
dispatchEvent @ react-dom\_client.js?v=b792a26f:16784
dispatchDiscreteEvent @ react-dom\_client.js?v=b792a26f:16765 <button>
exports.jsxDEV @ react\_jsx-dev-runtime.js?v=b792a26f:247
$RefreshSig$ @ ResultsScreen.tsx:1036
$RefreshSig$ @ ResultsScreen.tsx:989
react\_stack\_bottom\_frame @ react-dom\_client.js?v=b792a26f:18509
renderWithHooksAgain @ react-dom\_client.js?v=b792a26f:5729
renderWithHooks @ react-dom\_client.js?v=b792a26f:5665
updateFunctionComponent @ react-dom\_client.js?v=b792a26f:7475
beginWork @ react-dom\_client.js?v=b792a26f:8525
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
performUnitOfWork @ react-dom\_client.js?v=b792a26f:12561
workLoopSync @ react-dom\_client.js?v=b792a26f:12424
renderRootSync @ react-dom\_client.js?v=b792a26f:12408
performWorkOnRoot @ react-dom\_client.js?v=b792a26f:11766
performWorkOnRootViaSchedulerTask @ react-dom\_client.js?v=b792a26f:13505
performWorkUntilDeadline @ react-dom\_client.js?v=b792a26f:36 <ResultsScreen>
exports.jsxDEV @ react\_jsx-dev-runtime.js?v=b792a26f:247
AppContent @ App.tsx:306
react\_stack\_bottom\_frame @ react-dom\_client.js?v=b792a26f:18509
renderWithHooksAgain @ react-dom\_client.js?v=b792a26f:5729
renderWithHooks @ react-dom\_client.js?v=b792a26f:5665
updateFunctionComponent @ react-dom\_client.js?v=b792a26f:7475
beginWork @ react-dom\_client.js?v=b792a26f:8525
runWithFiberInDEV @ react-dom\_client.js?v=b792a26f:997
performUnitOfWork @ react-dom\_client.js?v=b792a26f:12561
workLoopSync @ react-dom\_client.js?v=b792a26f:12424
renderRootSync @ react-dom\_client.js?v=b792a26f:12408
performWorkOnRoot @ react-dom\_client.js?v=b792a26f:11766
performWorkOnRootViaSchedulerTask @ react-dom\_client.js?v=b792a26f:13505
performWorkUntilDeadline @ react-dom\_client.js?v=b792a26f:36
ResultsScreen.tsx:419 \[双轨制] ========== 服务器FFmpeg拼接+OSS上传结束 ==========
ResultsScreen.tsx:479 \[双轨制] 本地FFmpeg降级拼接: ✅ 成功
ResultsScreen.tsx:482 \[双轨制] ========== 双轨并行结束 ==========
ResultsScreen.tsx:159 \[缓存] 视频已在本地: combo\_cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34\_0
OptimizedVideoPlayer.tsx:62 \[OptimizedVideoPlayer] 使用本地缓存播放: combo\_cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34\_0
favicon.ico:1 GET <http://localhost:3000/favicon.ico> 404 (Not Found)
