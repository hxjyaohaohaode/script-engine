# Tasks: 互动影游剧本智能体集群 — 系统全方位深度优化

---

## 阶段一：基础设施加固与LLM服务升级

### - [ ] Task 1: LLM客户端完整升级
将 `backend/services/llm.py` 从当前基础版本升级为支持完整能力（三档思考模式、流式输出、速率限制、指数退避重试）的LLM调用封装。

- **SubTask 1.1**: 实现 `ThinkingMode` 枚举和对应的token预算配置（Non-think=0, Think High=8192, Think Max=32768）
- **SubTask 1.2**: 实现 `call_deepseek_v4()` 支持三档思考模式参数
- **SubTask 1.3**: 实现 `call_deepseek_reasoner()` CoT推理专用调用
- **SubTask 1.4**: 实现 `call_mimo_v25_pro()` 和 `call_mimo_v2_pro()` MiMo系列调用
- **SubTask 1.5**: 实现指数退避重试机制（1s→2s→4s，最多3次）
- **SubTask 1.6**: 实现API限流检测与排队等待（429响应处理）
- **SubTask 1.7**: 完善Mock降级响应（按Agent类型返回有意义的降级内容）

### - [ ] Task 2: 数据库连接池与查询优化
优化 `backend/database.py` 和所有API端点中的数据库操作。

- **SubTask 2.1**: 配置连接池参数（pool_size根据Render实例规格自适应）
- **SubTask 2.2**: 为高频查询添加数据库索引确认
- **SubTask 2.3**: 消除API中的N+1查询问题（使用joinedload/selectinload）
- **SubTask 2.4**: 实现异步批量操作（bulk_insert/bulk_update）

### - [ ] Task 3: 异步任务系统(Celery)完整实现
将 `backend/tasks/` 从空壳升级为完整的Celery异步任务管线。

- **SubTask 3.1**: 实现 `scene_generation.py`：异步场景生成任务（上下文组装→LLM调用→结果解析→数据库写入）
- **SubTask 3.2**: 实现 `scene_audit.py`：异步场景审计任务（程序化检测→LLM审计→结果汇总）
- **SubTask 3.3**: 实现 `full_audit.py`：全剧终审任务（伏笔回收率/时间线/结局可达性/角色弧/情感曲线/压力测试）
- **SubTask 3.4**: 实现 `foreshadow_design.py`：伏笔设计异步任务
- **SubTask 3.5**: 配置Celery worker（Redis broker + result backend）
- **SubTask 3.6**: 实现任务进度追踪（WebSocket推送 + 数据库状态更新）

### - [x] Task 4: WebSocket实时通信
实现前后端WebSocket通信，替代轮询方式。

- **SubTask 4.1**: FastAPI WebSocket端点实现（/ws/{project_id}）
- **SubTask 4.2**: 前端WebSocket Hook（自动重连、心跳检测）
- **SubTask 4.3**: 任务进度实时推送（AI生成/审计进度百分比）
- **SubTask 4.4**: Agent状态变更实时广播

### - [ ] Task 5: 安全加固
实施企业级安全措施。

- **SubTask 5.1**: API速率限制中间件（1分钟10次/项目）
- **SubTask 5.2**: 输入验证增强（Pydantic validators for all schemas）
- **SubTask 5.3**: SQL注入防护验证（确保所有查询使用参数化）
- **SubTask 5.4**: CORS策略收紧（仅允许已配置的前端域名）
- **SubTask 5.5**: 敏感操作审计日志（AI调用/删除操作/定稿操作记录）

---

## 阶段二：七大Agent核心能力实现

### - [ ] Task 6: 素材Agent完整实现【优先】
素材Agent是所有Agent中最重要的基础设施，其他Agent依赖其提供的上下文组装服务。

- **SubTask 6.1**: 实现上下文组装器 `ContextBuilder`（`backend/agents/context_builder.py`）
  - Layer 0不变量读取（从project_config表）
  - 前2个场景全文获取（从scenes表）
  - Layer 1角色状态获取（characters + character_relations + foreshadow_status + info_records）
  - Layer 3主线脉络读取（master-plan/文件系统）
  - Layer 4章节上下文获取（chapters表）
  - Layer 5场景摘要获取（scenes表摘要字段）
  - 三层结构裁剪算法（P1+P2不裁剪，P3-P6按优先级裁剪，总量≤3万字）
- **SubTask 6.2**: 实现文档管理器（Git版本控制）
  - 场景定稿后写入scripts/{scene_id}.yaml
  - git add + git commit（commit message包含场景信息）
  - 更新Layer 5 scene_index表
- **SubTask 6.3**: 实现索引查询器
  - 按角色查场景
  - 按伏笔ID查场景
  - 按关键词全文搜索
  - 按情感强度范围查询

### - [x] Task 7: 状态Agent完整实现
- **SubTask 7.1**: 实现状态更新器 `StateUpdater`
  - 解析scene_draft中的状态变化（角色情感/位置/已知信息）
  - 增量更新characters表中的动态字段
  - 更新foreshadow_status表（当前状态/强化次数）
  - 更新info_records表（新增信息点+知情角色列表）
  - 更新character_relations表（信任度/好感度变化）
  - 自洽检查（角色不双地点、关系值0-100、伏笔状态单向）
- **SubTask 7.2**: 实现伏笔追踪器 `ForeshadowTracker`
  - 遍历所有伏笔检查健康度（>5章未强化→警告，>10章未回收→危险）
  - 检查回收遗漏（已到计划回收位置但未回收）
  - 检查伏笔间依赖（A依赖B但B未揭露→告警）
- **SubTask 7.3**: 实现关系值管理器 `RelationManager`
  - 互动类型→关系值变化映射（正面/中性/负面/复杂各不同）
  - 关系值变化修正（高关系时正面效果+20%，低关系时负面效果+20%）
  - 引爆点检测（trust<20标记怀疑，trust骤降>50标记背叛事件）

### - [ ] Task 8: 审计Agent完整实现
- **SubTask 8.1**: 实现逻辑审计器 `LogicAuditor`
  - 阶段A：协调6个程序化检测器执行（全部通过才进入阶段B）
  - 阶段B：LLM审计（因果链推演/人设校验/对白风格校验）- 使用DS-Reasoner
  - 阶段C：创意评分（可预测性/情感冲击/节奏审计）- 仅含伏笔/反转的场景
  - 输出结构化审计报告（audit_report.yaml格式）
- **SubTask 8.2**: 实现全剧审计器 `FullAuditor`
  - 伏笔回收率统计（目标100%）
  - 时间线自洽检查（遍历所有场景时间标记）
  - 结局可达性分析（BFS从开局到每个结局）
  - 角色弧完整性分析（提取角色所有出场场景情感序列）
  - 全剧情感曲线分析（检测连续低谷/高峰/缺失）
  - 极端压力测试（重型模式：模拟3种玩家行为路径）

### - [ ] Task 9: 创作Agent完整实现
- **SubTask 9.1**: 实现场景撰写器 `SceneWriter`
  - 思考模式自动选择（普通过渡→Non-think / 情感冲突→Think High / 哇塞时刻→Think Max）
  - Prompt构建（Layer 0不变量 + Layer 1角色状态 + 前2场景全文 + 本场景任务要求）
  - LLM调用DS-V4-Pro
  - 结构化输出解析为scene_draft（scene_id/type/location/weather/characters/narration/dialogue/actions/foreshadow_ops/causal_chain/choices）
- **SubTask 9.2**: 实现对白生成器 `DialogueGenerator`
  - 读取角色语言风格/口头禅（Layer 0）
  - 读取情感状态和关系值（Layer 1）
  - 确定对白基调（关系×情感矩阵：4种基调）
  - 生成有区分度的对白+潜台词
- **SubTask 9.3**: 实现分支设计器 `BranchDesigner`
  - 分析核心冲突点
  - 设计2-3个选项（不同代价，非对/错）
  - 推演后果链（直接→间接→远期结果）
  - 设计隐藏选项（需特定前置条件）

### - [x] Task 10: 伏笔Agent完整实现
- **SubTask 10.1**: 实现三层伏笔设计器 `ForeshadowDesigner`
  - 从核心真相反推（6步推理法）
  - 生成全剧级伏笔5-8条（含三层含义+埋设/强化/揭露位置）
  - 生成章节级伏笔20-30条
  - 生成场景级伏笔60-100条
  - 设计伏笔间关联（DEPENDS_ON/SUPPORTS/ENABLES/CONFLICTS_WITH）
  - 输出为结构化数据写入数据库
- **SubTask 10.2**: 实现化学反应分析器 `ChemicalReactionAnalyzer`
  - 遍历伏笔对(A, B)分析组合效应
  - 判断1+1>2的伏笔对
  - 通知创意Agent评估是否设计新哇塞时刻

### - [ ] Task 11: 创意Agent完整实现
- **SubTask 11.1**: 实现哇塞方案设计器 `WowPlanDesigner`
  - 对每条全剧级伏笔尝试5种创意类型组合
  - 每个可行方案4维评分（可预测性/情感冲击/逻辑自洽/回望价值）
  - 每条伏笔保留2-3个最优方案
  - 输出结构化哇塞方案
- **SubTask 11.2**: 实现信息差设计器 `InfoGapDesigner`
  - 分析每条路线的可获得信息
  - 设计信息不对称分布
  - 确保单条路线体验完整、多条路线拼合有额外满足

### - [x] Task 12: 编排Agent完整实现
- **SubTask 12.1**: 实现任务拆解器 `TaskDecomposer`
  - 解析用户需求（题材/风格/字数/单人多人/核心创意）
  - 确定工作模式（轻量/标准/重型）
  - 生成Phase 0-6任务清单（标注依赖关系和优先级）
  - 输出task_list.yaml格式
- **SubTask 12.2**: 实现优先级调度器 `PriorityScheduler`
  - 从Layer 4获取当前章节待完成场景
  - 检查依赖链（前置已完成？）
  - 锚点场景优先
  - 有伏笔任务的场景优先
  - 根据情感曲线判断当前应上升还是下降
  - 输出优先级最高的场景ID + 创作要求
- **SubTask 12.3**: 实现冲突仲裁器 `ConflictArbiter`
  - 读取封驳原因和修改尝试
  - 判断逻辑问题（需改）vs 创意评判（需放宽）
  - 连续3次封驳 → 通知人类介入
- **SubTask 12.4**: 实现节奏监控器 `RhythmMonitor`
  - 统计情感强度序列
  - 连续2个≥8 → 下一个必须缓冲（≤4）
  - 连续3个≤4 → 下一个必须引爆（≥7）
  - 本章无哇塞时刻 → 标记需要
  - 违反规则 → 下达调整指令

---

## 阶段三：程序化检测器（6个）

### - [x] Task 13: 程序化检测器全部实现
6个检测器从 `backend/checkers/` 空壳实现为功能完备的检测模块。

- **SubTask 13.1**: 元素封闭性检测 `element_closure.py`
  - 从场景文本中提取所有专有名词（人名/地名/物品名/组织名）
  - 与element_registry表比对
  - 返回pass/fail + 未注册元素列表
- **SubTask 13.2**: 状态一致性检测 `state_consistency.py`
  - 比对scene_draft中的角色状态 vs Layer 1当前状态
  - 检查位置连续性（无瞬移）
  - 检查情感突变合理性（Δ>3需触发事件）
  - 检查信息获取合法性（角色不应知道未暴露的信息）
- **SubTask 13.3**: 伏笔状态机检测 `foreshadow_transition.py`
  - 定义合法状态转换表：design→plant, plant→reinforce/reveal, reinforce→reinforce/reveal, reveal→verify
  - 检查每个伏笔操作的状态转换合法性
- **SubTask 13.4**: 时空连续性检测 `spatiotemporal.py`
  - 检查时间不倒退
  - 检查地点跳跃时有足够的移动时间
- **SubTask 13.5**: 伏笔回收可达性检测 `foreshadow_reachability.py`
  - 从foreshadow_relations表读取伏笔间依赖图
  - BFS检查从plant_scene到reveal_scene的路径存在性
  - 列出所有断裂伏笔
- **SubTask 13.6**: 关系值连续性检测 `relation_continuity.py`
  - 检查关系值变化幅度（Δ>30需重大事件）
  - 检查关系值不越界（0-100）

---

## 阶段四：数据流闭环与API完善

### - [ ] Task 14: 项目仪表盘API实现
- **SubTask 14.1**: 实现 `GET /api/projects/{id}/dashboard` 端点
  - 返回：总字数（遍历所有场景narration字数总和）
  - 返回：场景数统计（按状态分组：total/draft/auditing/approved/final）
  - 返回：伏笔数统计（按类型/健康度分组）
  - 返回：角色数
  - 返回：各Phase完成进度百分比
  - 返回：最近10条活动记录

### - [x] Task 15: 场景定稿完整流程实现
- **SubTask 15.1**: 实现 `POST /api/projects/{id}/scenes/{sid}/finalize`
  - 验证场景状态为approved
  - 调用状态Agent更新Layer 1
  - 调用素材Agent写入Layer 2（Git commit）+ 更新Layer 5
  - 更新场景状态为final
  - 创建场景版本快照（scene_versions表）
  - 触发编排Agent推进下一个场景

### - [ ] Task 16: 伏笔系统API完善
- **SubTask 16.1**: 实现 `POST /api/projects/{id}/foreshadows/generate` 真实调用伏笔Agent
- **SubTask 16.2**: 实现 `POST /api/projects/{id}/foreshadows/{fid}/wow-plans` 真实调用创意Agent
- **SubTask 16.3**: 实现 `GET /api/projects/{id}/foreshadows/graph` 返回伏笔关联图谱数据
- **SubTask 16.4**: 实现 `GET /api/projects/{id}/foreshadows/health` 真实健康度计算
- **SubTask 16.5**: 实现 `POST /api/projects/{id}/foreshadows/chemical-reactions` 化学反应分析

### - [x] Task 17: 导出系统实现
- **SubTask 17.1**: 实现JSON格式导出（完整结构化数据）
- **SubTask 17.2**: 实现Markdown格式导出（可读剧本格式）
- **SubTask 17.3**: 实现纯文本导出（仅对白+叙述）
- **SubTask 17.4**: 实现Excel格式导出（场景/伏笔/角色表格）
- **SubTask 17.5**: 支持按章节/场景范围筛选导出
- **SubTask 17.6**: 支持勾选包含/排除审计报告和评分

### - [x] Task 18: 全剧终审API实现
- **SubTask 18.1**: 实现 `POST /api/projects/{id}/full-audit` 端点
  - 异步触发全剧审计任务
  - 返回任务ID供前端追踪
- **SubTask 18.2**: 实现 `GET /api/projects/{id}/audit-history` 审计历史查询
- **SubTask 18.3**: 实现 `GET /api/projects/{id}/timeline` 全剧时间线数据

---

## 阶段五：前端深度升级

### - [x] Task 19: 场景工作台对接真实API
将SceneWorkshop.tsx从Mock数据驱动升级为真实API驱动。

- **SubTask 19.1**: 替换MOCK_CHAPTERS为API查询（使用React Query）
- **SubTask 19.2**: AI生成调用真实后端Celery任务（显示WebSocket实时进度）
- **SubTask 19.3**: 审计提交对接真实审计API（显示程序化检测+LLM审计结果）
- **SubTask 19.4**: 定稿操作对接真实finalize API
- **SubTask 19.5**: 版本历史从数据库查询
- **SubTask 19.6**: 保存操作对接PUT API（自动保存+手动保存）

### - [ ] Task 20: 仪表盘数据动态化
- **SubTask 20.1**: 对接dashboard API获取真实统计数据
- **SubTask 20.2**: Phase进度条使用后端返回的实际百分比
- **SubTask 20.3**: 情感曲线预览使用真实数据（若存在）
- **SubTask 20.4**: 最近活动记录对接后端activity log

### - [ ] Task 21: 伏笔图谱可视化完整实现
- **SubTask 21.1**: 实现D3力导向图组件 `ForeshadowGraph.tsx`
  - 节点渲染（大小=级别，颜色=健康度）
  - 边渲染（实线/虚线/红线的样式区分）
  - 交互功能（缩放/拖拽/点击查看详情/搜索过滤）
- **SubTask 21.2**: 伏笔详情面板完善（三层结构展示/时间线/哇塞方案）

### - [ ] Task 22: 情感曲线页面升级
- **SubTask 22.1**: 使用Recharts实现全局情感曲线（标注哇塞时刻+节奏警告）
- **SubTask 22.2**: 章节详情展开（场景级情感条）
- **SubTask 22.3**: 节奏规则自动检测与可视化告警

### - [x] Task 23: 审核面板功能完善
- **SubTask 23.1**: 待审核列表实时更新
- **SubTask 23.2**: 封驳历史完整记录展示
- **SubTask 23.3**: 人类介入决策UI完善（4种决策选项 + 决策提交）

### - [x] Task 24: 全局加载/错误/边界处理
- **SubTask 24.1**: 网络断连检测组件（离线提示+操作暂存）
- **SubTask 24.2**: AI调用超时UI处理（进度条+取消按钮+超时提示）
- **SubTask 24.3**: 数据加载骨架屏（Skeleton占位替代空白Loading）
- **SubTask 24.4**: 空状态统一处理（Empty组件+引导文案）
- **SubTask 24.5**: 删除操作二次确认增强（显示关联影响）
- **SubTask 24.6**: 未保存离开确认（beforeunload + 路由守卫）
- **SubTask 24.7**: 响应式布局优化（移动端适配）
- **SubTask 24.8**: 深色模式完善（确保所有组件支持深色主题）

### - [x] Task 25: 前端性能优化
- **SubTask 25.1**: 路由级代码分割（React.lazy + Suspense）
- **SubTask 25.2**: 场景列表虚拟滚动（大数据量时）
- **SubTask 25.3**: React Query缓存策略优化（staleTime/cacheTime配置）
- **SubTask 25.4**: 图片/资源懒加载

---

## 阶段六：部署与验证

### - [x] Task 26: Render部署配置验证与优化
- **SubTask 26.1**: render.yaml配置验证与修复
- **SubTask 26.2**: Dockerfile优化（多阶段构建减小镜像体积）
- **SubTask 26.3**: 环境变量完整检查（DEV vs PROD配置分离）
- **SubTask 26.4**: 健康检查端点完善

### - [x] Task 27: 本地Docker开发环境完善
- **SubTask 27.1**: docker-compose.yml验证（PostgreSQL + Redis + Backend + Frontend + Celery worker）
- **SubTask 27.2**: 数据库初始化脚本完善（init_db.py）
- **SubTask 27.3**: 种子数据脚本完善（seed_data.py）

### - [x] Task 28: 全局集成测试与验证
- **SubTask 28.1**: 端到端场景创作流程测试（创建项目→世界观→角色→伏笔→章节→场景生成→审计→定稿）
- **SubTask 28.2**: AI调用成功/失败/超时各路径测试
- **SubTask 28.3**: 数据库迁移正确性验证
- **SubTask 28.4**: 前端所有页面功能完整性检查

---

# Task Dependencies

- **Task 6（素材Agent）** 是 Task 8（审计Agent）、Task 9（创作Agent）的前置依赖
- **Task 7（状态Agent）** 是 Task 8（审计Agent）、Task 15（定稿流程）的前置依赖
- **Task 13（程序化检测器）** 是 Task 8（审计Agent）的前置依赖
- **Task 1（LLM客户端升级）** 是 Task 6-12（所有Agent实现）的前置依赖
- **Task 3（Celery任务系统）** 是 Task 14-18（API完善）的前置依赖
- **Task 14-18（API完善）** 是 Task 19-24（前端升级）的前置依赖
- **Task 26-27（部署配置）** 可与阶段一~五并行开发
- **Task 28（集成测试）** 依赖所有其他任务完成
