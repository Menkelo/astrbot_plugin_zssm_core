# 需求文档 - 角色扮演模式

## 简介

为 zssm 插件新增角色扮演（Persona）功能，允许用户通过配置或指令切换 Bot 的回复风格和角色设定，满足不同场景的交互需求。

## 术语表

- **Persona（角色）**：一组预定义的系统提示词，决定 Bot 的回复语气、输出格式和行为风格
- **默认 Persona**：插件配置中指定的固定角色，未通过指令切换时使用
- **临时 Persona**：通过指令参数指定的角色，仅对当次请求生效

---

## 需求

### R1 - 内置 Persona 预设

**User Story:** 作为用户，我希望插件内置几套常用角色，无需手动编写提示词即可快速切换 Bot 风格。

#### 验收标准

1. The system SHALL provide at least 2 built-in persona presets, each with a unique identifier
2. Each persona preset SHALL include a complete system prompt defining the role, tone, and output format
3. WHEN a preset is loaded, the persona system prompt SHALL replace the default system prompt entirely
4. The built-in presets SHALL include: 猫娘(catgirl), 梗百科(meme-expert)

---

### R2 - 配置固定默认 Persona

**User Story:** 作为群管理员，我希望在插件配置中指定一个默认角色，让所有 zssm 请求统一使用该角色风格回复。

#### 验收标准

1. The configuration SHALL include a `default_persona` field with a dropdown selector listing all available personas
2. WHEN `default_persona` is set to a valid persona, the system SHALL use that persona's system prompt for all requests
3. WHEN `default_persona` is empty, the system SHALL use the original default system prompt ("中文助理")

---

### R3 - 指令参数临时切换 Persona

**User Story:** 作为普通用户，我希望在发送 zssm 时通过参数临时指定角色，让当次回复使用对应风格。

#### 验收标准

1. WHEN user sends `/zssm --persona <id>` or `/zssm -p <id>`, the system SHALL use the specified persona for that request only
2. The `--persona` parameter SHALL accept persona IDs matching the built-in presets
3. IF the specified persona ID does not exist, the system SHALL reply with available persona list and fall back to the default persona
4. The `--persona` parameter SHALL take precedence over the configured `default_persona`

---

### R4 - 查询可用 Persona 列表

**User Story:** 作为用户，我希望通过指令查看当前有哪些可用角色可供选择。

#### 验收标准

1. WHEN user sends `/zssm --list-persona` or `/zssm -l`, the system SHALL reply with all available persona names and their IDs
2. The list SHALL include each persona's ID and a one-line description

---

### R5 - 关键词触发兼容

**User Story:** 作为用户，我希望通过 `zssm -p catgirl 解释这段话` 这样的关键词触发方式也能切换角色。

#### 验收标准

1. WHEN keyword trigger detects `zssm -p <id>` or `zssm --persona <id>`, the system SHALL parse and apply the persona parameter
2. The persona parameter parsing SHALL work identically for both command and keyword trigger paths
