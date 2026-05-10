# Tasks: 互动影游剧本质量全面重构

---

## 阶段一：世界观数据流修复与同步

### - [x] Task 1: 修复流水线世界观生成→数据库写入的数据流
流水线Phase 0的`world_builder`步骤生成的世界观内容必须正确写入`project_config`表的`custom_checker_rules.world_settings`字段。

- **SubTask 1.1**: 检查`backend/core/agent/creator.py`中`world_builder`技能的输出处理逻辑，确保8个世界观配置项（core_contradiction/social_structure/tech_magic/geography/history/culture/constraints/impossible）的生成结果写入`project_config.custom_checker_rules.world_settings`
- **SubTask 1.2**: 修复`backend/api/ai.py`中`generate_world_config`端点，确保AI生成方案后自动保存到数据库（当前仅返回proposals但不自动写入）
- **SubTask 1.3**: 在流水线`world_builder`步骤完成后，通过WebSocket广播`WORLD_CONFIG_UPDATED`事件，触发前端刷新
- **SubTask 1.4**: 验证前端`WorldSettings.tsx`的`fetchConfigs`能正确读取`project_config`表中已同步的世界观数据

### - [x] Task 2: 世界观AI生成Prompt优化
升级世界观生成Prompt，确保生成内容与已有设定深度关联，符合"洋葱模型"标准。

- **SubTask 2.1**: 优化`build_world_gen_prompt`，增加"必须引用其他已锁定设定"的约束，确保每个方案都能衍生出角色动机和剧情冲突
- **SubTask 2.2**: 增加"互动影游适配性"检查：每个世界观设定必须标注"如何影响玩家选择"和"如何制造分支"
- **SubTask 2.3**: 增加世界观配置项之间的交叉引用提示（如：生成"社会结构"时必须引用"核心矛盾"和"约束条件"）

---

## 阶段二：角色关系网络升级

### - [x] Task 3: 角色关系网络密度与质量升级
升级角色生成和关系网络生成逻辑，确保关系密度达标且与世界观深度关联。

- **SubTask 3.1**: 优化`build_character_gen_prompt`，增加"每个角色的核心动机必须与世界观核心矛盾直接关联"的约束
- **SubTask 3.2**: 优化`build_relation_network_prompt`，增加"关系密度不低于60%"的约束，确保N个角色至少生成N*(N-1)/2*0.6条关系
- **SubTask 3.3**: 在关系网络Prompt中增加"信息不对称"设计：每条关系必须包含A知道B什么/B知道A什么
- **SubTask 3.4**: 增加"暗线关系"生成：至少20%的关系为暗线类型（secret_ally/hidden_enemy/blackmailer等）
- **SubTask 3.5**: 增加"关系弧线预规划"：每条关系标注预期变化方向（改善/恶化/稳定）和引爆点条件

### - [x] Task 4: 角色关系图谱可视化升级
升级前端角色关系图谱，增加关系弧线和引爆点可视化。

- **SubTask 4.1**: 在关系连线上增加方向箭头和趋势标记（↑改善/↓恶化/→稳定）
- **SubTask 4.2**: 引爆点（trust骤降>30的场景）用红色爆炸图标标记在连线上
- **SubTask 4.3**: 暗线关系用紫色虚线+锁图标标记，需特定场景触发后才解锁显示
- **SubTask 4.4**: 点击连线弹出"关系弧线时间轴"面板，展示关系值随场景的变化轨迹
- **SubTask 4.5**: 增加关系网络密度统计指标（当前密度/目标密度/孤立角色数）

---

## 阶段三：伏笔体系全面重构

### - [x] Task 5: 伏笔生成Prompt与逻辑重构
重构伏笔Agent和生成Prompt，确保生成三层伏笔体系且与世界观/角色/场景深度关联。

- **SubTask 5.1**: 重构`backend/core/agent/foreshadow.py`的`foreshadow_designer`技能，实现从核心真相反推的三层伏笔设计
- **SubTask 5.2**: 重构伏笔生成Prompt，确保生成全剧级5-8条/章节级20-30条/场景级60-100条
- **SubTask 5.3**: 每条伏笔必须包含三层含义（surface_layer/deep_layer/truth_layer）+ 哇塞方案预设计 + 关联世界观设定ID + 关联角色ID
- **SubTask 5.4**: 伏笔间必须建立四类关联（DEPENDS_ON/SUPPORTS/ENABLES/CONFLICTS_WITH），关联密度不低于伏笔数的1.5倍
- **SubTask 5.5**: 伏笔必须标注与世界观设定的关联（如：此伏笔揭露了"科技体系"的深层规则）
- **SubTask 5.6**: 伏笔必须标注与角色的关联（如：此伏笔涉及角色A的暗秘密）
- **SubTask 5.7**: 核心伏笔回收率规划不低于80%，在生成时即规划plant→reinforce→reveal的完整路径

### - [x] Task 6: 哇塞方案设计升级
升级哇塞方案设计，确保与核心真相直接关联且评分标准严格。

- **SubTask 6.1**: 重构`build_wow_plan_prompt`，增加5种创意类型（反转/信息差/角色弧光/世界观颠覆/情感核弹）
- **SubTask 6.2**: 每个方案4维评分：可预测性(3-7)/情感冲击(≥8)/逻辑自洽(≥8)/回望价值(≥7)
- **SubTask 6.3**: 哇塞方案必须标注与核心真相的关联路径
- **SubTask 6.4**: 哇塞方案必须包含"回望线索"设计——玩家回顾时能发现的暗示

### - [x] Task 7: 伏笔关联弧线可视化
在伏笔页面增加"联系弧线"可视化，展示伏笔→角色→场景→世界观的全链路关联。

- **SubTask 7.1**: 在伏笔详情面板增加"关联世界观"标签，显示此伏笔揭露/引用的世界观设定
- **SubTask 7.2**: 在伏笔详情面板增加"关联角色"标签，显示此伏笔涉及的角色及其暗秘密
- **SubTask 7.3**: 在伏笔图谱中增加"联系弧线"模式：点击伏笔节点时高亮显示从世界观→角色→伏笔→场景的完整路径
- **SubTask 7.4**: 在伏笔图谱中增加"关联密度"统计：显示每个伏笔的关联数量和健康度

---

## 阶段四：章节结构与互动选择重构

### - [x] Task 8: 章节"节"数据模型与API
新增章节"节"（Section）数据模型，支持每章2-5个互动节点。

- **SubTask 8.1**: 在`backend/models/chapter.py`中新增`ChapterSection`模型：section_number/title/word_target/emotion_target/scene_ids/choices/foreshadow_tasks/focus_characters/branch_type
- **SubTask 8.2**: 创建数据库迁移脚本，新增`chapter_sections`表
- **SubTask 8.3**: 新增章节Section CRUD API：`POST/GET/PUT/DELETE /api/projects/{id}/chapters/{cid}/sections`
- **SubTask 8.4**: 修改章节API返回数据，包含sections列表

### - [x] Task 9: 章节AI展开升级
重构章节大纲AI生成逻辑，生成包含节、互动选择、伏笔任务的完整章节结构。

- **SubTask 9.1**: 重构`build_chapter_outline_prompt`，增加"每章2-5个节"的结构要求
- **SubTask 9.2**: 每个节必须包含：标题/目标字数/情感目标/涉及角色/伏笔任务/互动选择设计
- **SubTask 9.3**: 章节生成必须关联世界观设定（标注引用了哪些世界观配置项）
- **SubTask 9.4**: 章节生成必须标注聚焦角色及其关系变化预期
- **SubTask 9.5**: 章节生成必须标注伏笔任务（哪些伏笔需在此章埋设/强化/回收）
- **SubTask 9.6**: 章节字数根据项目目标字数和章节数自动分配
- **SubTask 9.7**: 节的排列遵循"漏斗模型"：开头自由探索→中段关键抉择→结尾汇入主线

### - [x] Task 10: 互动选择设计系统
实现完整的互动选择设计，包含差异化选项、后果链推演、隐藏选项。

- **SubTask 10.1**: 新增`ChoiceDesign`数据模型：choice_id/section_id/text/consequence_direct/consequence_indirect/consequence_long_term/character_impact/is_hidden/hidden_condition
- **SubTask 10.2**: 在章节AI展开Prompt中增加互动选择设计要求：2-3个差异化选项+1个隐藏选项
- **SubTask 10.3**: 每个选择必须包含后果链推演：直接后果→间接后果→远期后果
- **SubTask 10.4**: 选择设计遵循"道德灰度"原则：没有完美答案，每个选择都有代价
- **SubTask 10.5**: 分支层级控制在3-4级以内，避免剧情过度分散
- **SubTask 10.6**: 新增互动选择API：`POST/GET/PUT/DELETE /api/projects/{id}/chapters/{cid}/sections/{sid}/choices`

### - [x] Task 11: 章节大纲前端升级
升级ChapterOutline页面，展示章节的节结构和互动选择。

- **SubTask 11.1**: 章节卡片展开后显示节列表（Section），每节显示标题/字数/情感目标/互动选择数
- **SubTask 11.2**: 节详情面板显示：互动选择列表（选项文本+后果预览）、伏笔任务、聚焦角色
- **SubTask 11.3**: 章节卡片增加世界观关联标签（标注引用了哪些世界观设定）
- **SubTask 11.4**: 章节卡片增加伏笔任务标签（🌱埋设/🔄强化/💡回收）
- **SubTask 11.5**: AI展开大纲按钮生成包含节的完整章节结构

---

## 阶段五：完整剧本生成与互动要素

### - [x] Task 12: 场景生成Prompt升级
升级场景生成Prompt，确保生成内容包含完整的互动要素。

- **SubTask 12.1**: 场景叙述必须包含画面感+感官描写（至少两种感官）
- **SubTask 12.2**: 对白必须包含潜台词（字面意思与真实意图的落差）
- **SubTask 12.3**: 对白必须反映角色语言风格和口头禅
- **SubTask 12.4**: 互动选择必须包含2-3个选项+后果推演（直接/间接/远期）
- **SubTask 12.5**: 伏笔操作必须标注操作类型（plant/reinforce/reveal）和涉及的伏笔ID+关联世界观设定
- **SubTask 12.6**: 因果链必须包含：前置条件→催化剂→直接结果→间接结果→远期结果
- **SubTask 12.7**: 场景生成必须引用上下文：前2场景全文+世界观+角色状态+伏笔任务

### - [x] Task 13: 剧本预览页面升级
升级ScriptPreview页面，以互动影游格式展示完整剧本。

- **SubTask 13.1**: 场景叙述用沉浸式排版展示（背景描述+角色动作+对白）
- **SubTask 13.2**: 选择点用高亮卡片展示，可点击查看各选项的后果链
- **SubTask 13.3**: 伏笔操作用特殊标记显示（🌱埋设/🔄强化/💡回收）
- **SubTask 13.4**: 哇塞时刻用★标记，点击可查看哇塞方案详情
- **SubTask 13.5**: 支持按章节/角色/伏笔筛选查看
- **SubTask 13.6**: 支持"模拟游玩"模式：用户可以做出选择，查看对应分支的剧情走向

### - [x] Task 14: 导出系统互动标记升级
升级导出系统，确保导出内容包含完整的互动标记。

- **SubTask 14.1**: Markdown导出增加互动标记：[CHOICE]选择点 / [BRANCH]分支 / [CONSEQUENCE]后果 / [FORESHADOW]伏笔操作
- **SubTask 14.2**: JSON导出包含完整的结构化互动数据（choices/branches/consequences/foreshadow_ops/character_state_changes）
- **SubTask 14.3**: 导出内容包含章节的节结构（sections）和互动选择（choices）
- **SubTask 14.4**: 导出内容包含伏笔关联弧线（世界观→角色→伏笔→场景的完整路径）

---

## 阶段六：流水线模板升级

### - [x] Task 15: 流水线模板升级
升级`interactive_drama.yaml`模板，确保流水线生成完整的互动影游剧本。

- **SubTask 15.1**: Phase 0（设定）增加世界观→数据库写入步骤，确保生成内容持久化
- **SubTask 15.2**: Phase 0（设定）增加伏笔三层体系设计步骤（全剧级→章节级→场景级）
- **SubTask 15.3**: Phase 1（大纲）升级为生成包含节结构和互动选择的完整大纲
- **SubTask 15.4**: Phase 2（场景创作）升级为生成包含完整互动要素的场景
- **SubTask 15.5**: 新增Phase 2.5（互动设计）：基于场景内容设计互动选择和分支路径
- **SubTask 15.6**: Phase 3（终审）增加互动要素审计：选择有效性/分支可达性/后果一致性

---

# Task Dependencies

- **Task 1（世界观数据流修复）** 是 Task 2/3/5/9 的前置依赖（世界观数据必须先同步）
- **Task 3（角色关系网络升级）** 依赖 Task 1（需要世界观上下文）
- **Task 5（伏笔体系重构）** 依赖 Task 1 + Task 3（需要世界观和角色数据）
- **Task 8（节数据模型）** 是 Task 9/10/11 的前置依赖
- **Task 9（章节AI展开升级）** 依赖 Task 1 + Task 3 + Task 5 + Task 8
- **Task 10（互动选择设计）** 依赖 Task 8
- **Task 12（场景生成升级）** 依赖 Task 1 + Task 3 + Task 5
- **Task 13（剧本预览升级）** 依赖 Task 12
- **Task 14（导出升级）** 依赖 Task 8 + Task 10
- **Task 15（流水线模板升级）** 依赖 Task 1-14 全部完成
- **Task 4/6/7/11**（前端可视化升级）可与对应后端任务并行开发
