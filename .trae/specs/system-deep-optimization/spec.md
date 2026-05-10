# 互动影游剧本智能体集群 — 系统全方位深度优化

> **日期**: 2026-05-03
> **基于**: `完整技术方案.md` + `开发规格书.md`
> **范围**: 全系统深度优化，覆盖功能完整性、性能效率、安全性、可靠性、易用性、可维护性六大维度

---

## Why

当前系统已建立基础骨架（FastAPI后端 + React前端 + 数据库模型），但核心业务逻辑几乎全部为空壳或Mock实现。7个Agent的实际能力、6个程序化检测器、上下文组装器、Celery异步任务管线、AI真实验证流程、伏笔图谱、情感曲线引擎等关键模块均未实现。此外，前端与后端之间存在大量脱节，Mock数据充斥界面，缺乏真实的数据流闭环。必须执行全方位深度优化，使系统达到 `完整技术方案.md` 和 `开发规格书.md` 中定义的企业级标准。

## What Changes

### 核心Agent实现（7个Agent全部从空壳升级为完整实现）
- **编排Agent**: 任务拆解器、优先级调度器、冲突仲裁器、节奏监控器
- **创作Agent**: 场景撰写器、对白生成器、分支设计器（支持Non-think/Think High/Think Max三档思考）
- **审计Agent**: 逻辑审计器（协调6项程序化检测+3项LLM审计）、全剧审计器（伏笔回收率/时间线/结局可达性/角色弧/情感曲线/压力测试）
- **状态Agent**: 状态更新器（Layer 1增量更新）、伏笔追踪器、关系值管理器
- **素材Agent**: 上下文组装器（六层记忆结构+裁剪算法）、文档管理器（Git版本控制）、索引查询器
- **伏笔Agent**: 三层伏笔设计器（全剧/章节/场景级）、化学反应分析器
- **创意Agent**: 哇塞方案设计器（5种创意类型）、信息差设计器

### 程序化检测器实现（6个从空壳升级为完整实现）
- 元素封闭性检测
- 状态一致性检测
- 伏笔状态机检测
- 时空连续性检测
- 伏笔回收可达性检测（BFS图算法）
- 关系值连续性检测

### 数据流闭环打通
- **BREAKING**: 前端Mock数据全部替换为真实API调用
- 场景生成 → 审计 → 封驳/通过 → 定稿 → Layer 1/2/5写入的完整流水线
- WebSocket/SSE实时进度推送（替代轮询）
- Agent间通过消息总线（Redis Pub/Sub）通信

### 伏笔系统升级
- 伏笔关系图谱（D3力导向图）完整实现
- 伏笔健康度实时监控与预警
- 伏笔化学反应自动分析与建议
- 伏笔状态机严格校验

### 情感曲线引擎
- 基于Recharts的全剧情感曲线可视化
- AI驱动的自动情感标注
- 节奏规则自动检测与告警（连续高潮/低谷/峰值缺失）

### 审核与导出系统
- 完整审核面板（待审核/已封驳/已通过/需人工介入）
- 连续3次封驳自动升级人类介入
- 多格式导出（JSON/Markdown/纯文本/Excel）
- Git版本历史完整追踪

### 安全加固
- API Key安全存储（环境变量，前端不可见）
- 输入验证与注入防护
- CORS策略收紧
- 速率限制（防API滥用）
- 敏感操作审计日志

### 可靠性提升
- 全局错误边界（前后端）
- 网络断连检测与自动重连
- AI调用超时/失败自动重试（指数退避）
- 数据定期自动备份策略
- 断路器模式防止级联故障

### 性能优化
- 数据库查询优化（N+1消除、索引覆盖）
- 上下文组装缓存（Redis）
- 前端虚拟滚动（大数据量场景列表）
- 前端代码分割与懒加载
- AI调用并发控制与优先级队列

## Impact

- Affected specs: N/A（首次完整实现）
- Affected code: 几乎所有模块（backend/agents/*, backend/checkers/*, backend/services/*, backend/tasks/*, backend/api/*, frontend/src/pages/*, frontend/src/components/*, frontend/src/stores/*, frontend/src/api/client.ts）

---

## ADDED Requirements

### Requirement: 七Agent完整能力体系
系统 SHALL 提供7个具备完整AI推理能力的Agent，每个Agent对应明确职责，通过消息总线协作完成剧本生产全流程。

#### Scenario: 编排Agent调度场景创作
- **GIVEN** 项目处于Phase 5（场景创作阶段）
- **WHEN** 一个场景定稿完成
- **THEN** 编排Agent自动选择下一个最优场景（锚点优先 > 伏笔任务 > 依赖链最短）
- **AND** 通过消息总线向素材Agent请求上下文组装
- **AND** 将组装好的上下文+创作要求派发给创作Agent

#### Scenario: 创作Agent按模式生成
- **GIVEN** 创作Agent收到场景创作任务
- **WHEN** 场景为哇塞时刻
- **THEN** 使用Think Max模式（32K token思考预算）
- **AND** Prompt包含完整Layer 0不变量 + 前2场景全文 + 哇塞方案详细要求

#### Scenario: 审计Agent执行全链路审计
- **GIVEN** 创作Agent提交场景初稿
- **WHEN** 审计Agent接收审核任务
- **THEN** 先执行6项程序化检测（代码层面，成本为零）
- **AND** 程序化检测全部通过后执行LLM审计（6项CoT推理）
- **AND** 输出结构化审计报告（pass/fail + 问题列表 + 修改建议）

#### Scenario: 状态Agent增量更新
- **GIVEN** 场景通过审计并定稿
- **WHEN** 状态Agent收到定稿通知
- **THEN** 增量更新Layer 1（角色状态/伏笔状态/信息记录/关系值）
- **AND** 自洽检查（同一角色不双地点、关系值不越界、伏笔状态单向）
- **AND** 广播 state.update 事件

#### Scenario: 素材Agent上下文裁剪
- **GIVEN** 目标场景ID
- **WHEN** 素材Agent组装上下文包
- **THEN** 必须包含 Layer 0 全部 + 前2个场景全文（不可裁剪）
- **AND** 按需包含 Layer 1/3/4/5 内容
- **AND** 总量超过3万字时按优先级裁剪（P6→P5→P4→P3）
- **AND** P1和P2绝不裁剪

#### Scenario: 伏笔Agent设计三层体系
- **GIVEN** 项目核心真相已定义
- **WHEN** 用户请求AI设计伏笔
- **THEN** 从核心真相反推：全剧级5-8条 + 章节级20-30条 + 场景级60-100条
- **AND** 每条伏笔包含三层含义（表面/深层/真相）
- **AND** 设计伏笔间关联图（DEPENDS_ON/SUPPORTS/ENABLES/CONFLICTS_WITH）

#### Scenario: 创意Agent设计哇塞方案
- **GIVEN** 全剧级伏笔已定义
- **WHEN** 用户请求哇塞方案
- **THEN** 对每条全剧级伏笔尝试5种创意类型组合
- **AND** 每个可行方案评估：可预测性(3-7)/情感冲击(≥8)/逻辑自洽(≥8)/回望价值(≥7)
- **AND** 每条伏笔保留2-3个最优方案供人类选择

### Requirement: 六项程序化检测器
系统 SHALL 提供6个程序化检测器，在场景审计阶段A自动执行，不消耗LLM Token，任一失败直接封驳。

#### Scenario: 元素封闭性检测
- **GIVEN** 场景文本和元素注册表
- **WHEN** 检测器扫描场景中所有专有名词（人名/地名/物品名/组织名/事件名）
- **THEN** 全部∈元素注册表 → Pass
- **AND** 发现有未注册元素 → Fail并列出未注册项

#### Scenario: 状态一致性检测
- **GIVEN** 场景角色状态和Layer 1当前状态
- **WHEN** 比对角色位置/情感/已知信息
- **THEN** 位置不一致且无移动描写 → Fail
- **AND** 情感突变(Δ>3)无触发事件 → Fail
- **AND** 角色知道不应知道的信息 → Fail

#### Scenario: 伏笔状态机检测
- **GIVEN** 场景中的伏笔操作和当前伏笔状态
- **WHEN** 检查状态转换合法性
- **THEN** design→plant, plant→reinforce/reveal, reinforce→reinforce/reveal, reveal→verify
- **AND** 不合法转换 → Fail

#### Scenario: 时空连续性检测
- **GIVEN** 新场景与前序场景的时间/地点
- **WHEN** 检查时空跳变
- **THEN** 时间倒流 → Fail
- **AND** 地点跳跃但时间差 < 两地最短移动时间 → Fail

#### Scenario: 伏笔回收可达性检测
- **GIVEN** 所有伏笔状态和场景依赖图
- **WHEN** BFS遍历从plant_scene到reveal_scene的路径
- **THEN** 存在通路 → Pass
- **AND** 无通路 → Fail并列出断裂伏笔

#### Scenario: 关系值连续性检测
- **GIVEN** 场景中的角色互动和Layer 1关系值
- **WHEN** 检查关系变化幅度
- **THEN** 信任度Δ>30且无重大事件支撑 → Fail
- **AND** 关系值不越界(0-100)

### Requirement: 全功能审核面板
系统 SHALL 提供完整的审核管理界面，支持待审核列表、审计详情查看、人类介入决策。

#### Scenario: 审计封驳与重试
- **GIVEN** 场景审计未通过
- **WHEN** 审计Agent返回封驳结果
- **THEN** 前端红色高亮显示问题项
- **AND** 创作Agent自动收到修改任务
- **AND** 重新提交后再次审计

#### Scenario: 连续封驳升级
- **GIVEN** 同一场景连续3次审计未通过
- **WHEN** 第3次封驳发生
- **THEN** 系统弹出"需要人类介入"弹窗
- **AND** 附带3次封驳的完整历史
- **AND** 提供4种决策选项（接受/按建议修改/人工编辑/重新生成）

### Requirement: 伏笔关系图谱可视化
系统 SHALL 提供基于D3力导向图的伏笔关联可视化。

#### Scenario: 伏笔图谱交互
- **GIVEN** 项目有多个伏笔和关联关系
- **WHEN** 用户打开伏笔管理页面
- **THEN** 展示力导向图（节点=伏笔，边=关联类型）
- **AND** 节点颜色表示健康度（绿=正常/黄=警告/红=危险）
- **AND** 节点大小表示伏笔级别（全剧级>章节级>场景级）
- **AND** 边类型可视化区分（实线=supports/虚线=depends_on/红线=conflicts）
- **AND** 支持缩放、拖拽、点击查看详情

### Requirement: 情感曲线可视化与节奏检测
系统 SHALL 提供全剧情感曲线可视化，并自动检测节奏违规。

#### Scenario: 节奏违规告警
- **GIVEN** 章节场景情感数据已录入
- **WHEN** 情感曲线页面渲染
- **THEN** 连续3个场景≥8 → 红色警告"疲劳风险"+建议插入缓冲
- **AND** 连续3个场景≤4 → 黄色警告"无聊风险"+建议提前引爆
- **AND** 某章无峰值 → 橙色警告"本章缺少高潮"
- **AND** 哇塞时刻间隔<2章 → 提示"过于密集"

### Requirement: 多格式导出系统
系统 SHALL 支持JSON、Markdown、纯文本、Excel四种格式的项目数据导出。

#### Scenario: 选定范围导出
- **GIVEN** 项目有多个章节和场景
- **WHEN** 用户选择特定章节和场景范围
- **THEN** 导出内容仅包含选定范围
- **AND** 支持选择包含/排除审计报告和评分数据

### Requirement: 系统安全加固
系统 SHALL 实施企业级安全措施。

#### Scenario: API Key保护
- **GIVEN** DeepSeek和MiMo API Key配置在服务端环境变量
- **WHEN** 前端发起AI生成请求
- **THEN** API Key绝不出现在前端响应中
- **AND** AI调用完全由后端代理

#### Scenario: 速率限制
- **GIVEN** 用户频繁触发AI操作
- **WHEN** 同一项目在1分钟内超过10次AI调用
- **THEN** 返回429状态码
- **AND** 前端显示"请求过于频繁，请稍后重试"

### Requirement: 系统可靠性保障
系统 SHALL 提供多层容错机制确保服务稳定。

#### Scenario: AI调用失败自动重试
- **GIVEN** AI API调用超时或返回5xx错误
- **WHEN** 第一次调用失败
- **THEN** 自动重试（指数退避：1s→2s→4s，最多3次）
- **AND** 全部失败后使用Mock降级响应
- **AND** 前端显示"AI服务暂时不可用，已使用备用方案"

## MODIFIED Requirements

### Requirement: 场景工作台升级
原场景工作台使用大量Mock数据和本地状态。**修改为**：场景工作台完全对接后端API，支持真正的AI生成→审计→定稿流程，数据持久化到PostgreSQL。

#### Scenario: 场景数据真实持久化
- **GIVEN** 用户编辑场景内容
- **WHEN** 点击保存或触发AI生成
- **THEN** 数据通过PUT/POST请求持久化到后端数据库
- **AND** 页面刷新后数据不丢失

### Requirement: 项目仪表盘数据动态化
原仪表盘的统计卡片、进度条、Agent状态均为静态零值。**修改为**：仪表盘数据从后端实时查询，展示真实项目状态。

#### Scenario: 仪表盘实时数据
- **GIVEN** 用户进入仪表盘
- **WHEN** 页面加载完成
- **THEN** 总字数/场景数/伏笔数/角色数显示真实值
- **AND** Phase进度条反映实际完成状态
- **AND** Agent状态面板显示实际运行状态
- **AND** 情感曲线预览使用真实数据

### Requirement: AI接口从Mock升级为真实LLM调用
所有AI接口当前返回硬编码Mock数据。**修改为**：AI接口通过httpx调用DeepSeek API和MiMo API，替换Mock为真实LLM响应。

#### Scenario: 真实AI场景生成
- **GIVEN** 已配置DEEPSEEK_API_KEY
- **WHEN** 用户触发场景生成
- **THEN** 后端通过Celery异步任务调用DeepSeek V4 Pro API
- **AND** 返回LLM生成的场景内容
- **AND** 如API Key未配置则降级为Mock响应

---

## REMOVED Requirements

无移除的需求。本次为从骨架到完整的增量升级，不删除任何已有设计。
