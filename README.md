# 翻译 Agent — 发布部署说明

本项目提供 **两种发布形态**，可按需选择：

| 形态 | 目录 | 特点 | 适用场景 |
|------|------|------|----------|
| **完整版 (Flask)** | 项目根目录 | 文本翻译 + **文档翻译（PDF/Word）** + **术语表 / 翻译记忆 / 多引擎** | 自建服务器 / Docker / 云主机 |
| **纯前端演示版** | `static-demo/` | 零后端依赖，文本翻译（词典数据本地加载） | 静态托管（GitHub Pages、Vercel、CloudStudio 等） |

> **文档翻译与提效功能仅完整版支持**：依赖后端 Python 库，纯前端版不含。

## 工作提效功能（三件套）

在 Web 界面右上角「⚙ 设置」中配置：

### 1. 自定义术语表
- 行业黑话强制使用指定译法（如 `KPI → 关键绩效指标`）
- 支持英→中、中→英两个方向，词边界匹配，Web 界面直接增删
- 数据保存在 `translator/data/glossary.json`

### 2. 翻译记忆 (TM)
- 重复句子自动复用历史译文：二次翻译秒回、长文档前后一致
- SQLite 存储（`translator/data/tm.sqlite`），自动记录每次译文
- 界面可查看统计/一键清空

### 3. 自定义 API Key（多引擎）
| 引擎 | 特点 | 需要配置 |
|------|------|---------|
| MyMemory | 免费公共接口（默认） | 无 |
| DeepL | 质量高、免费版可用 | API Key |
| 百度翻译 | 国内访问快 | APP_ID + 密钥 |
| 腾讯云 TMT | 腾讯生态 | SecretId + SecretKey |
| OpenAI 兼容 | 质量最高（可接 DeepSeek/通义） | API Key + 接口地址 |

- 未配置 Key 的引擎自动回退 MyMemory；Key 保存在本机 `translator/data/settings.json`
- 也可直接在 `config.py` 中配置（环境变量/常量）

## 一、完整版部署

### 1. 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python run.py
# 访问 http://localhost:5000
```

### 2. Docker 一键部署

```bash
docker build -t english-translator .
docker run -d -p 5000:5000 --name translator english-translator
```

### 3. 常用云平台部署指引

- **阿里云/腾讯云 ECS、轻量服务器**：安装 Docker 后执行上述命令，并在安全组开放 5000 端口
- **腾讯云 CloudBase / 云函数**：项目内置了 `Dockerfile`，可通过容器镜像方式部署；也可以将 `translator/web/static/` 前端部分托管为静态资源，后端 API 单独部署
- **任意 PaaS 平台**（Railway / Fly.io 等）：直接关联本仓库，启动命令 `python run.py`

### 4. 配置说明 (`config.py`)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ONLINE_TRANSLATE_ENABLED` | `True` | 在线增强开关（MyMemory 免费 API，无需 Key） |
| `TRANSLATOR_PROVIDER` | `mymemory` | 默认翻译引擎（mymemory/deepl/baidu/tencent/openai） |
| `DEEPL_API_KEY` 等 | `""` | 各引擎 Key（也可在 Web 设置面板配置） |
| `TM_ENABLED` | `True` | 翻译记忆开关 |
| `GLOSSARY_ENABLED` | `True` | 术语表开关 |
| `MAX_INPUT_LEN` | 5000 | 单次最大输入字符数 |
| `HOST` / `PORT` | `0.0.0.0` / `5000` | 服务监听地址/端口 |

## 二、纯前端演示版发布

`static-demo/` 目录是**零依赖**的静态站点，可直接上传到任意静态托管平台：

```bash
# 把 static-demo 目录部署到任意静态托管
# 例如 GitHub Pages / Vercel / Netlify / CloudStudio
```

> 提示：如需重新生成精简词典数据 `js/dict.js`：
> ```bash
> python scripts/build_js_demo.py 12000
> ```

## 三、文档翻译（PDF / Word）

在 Web 界面切换至「文档翻译」页签，或直接调用下述 API。

### 支持格式与限制

| 格式 | 支持 | 说明 |
|------|------|------|
| `.pdf` | ✅ | 文本型 PDF 直接提取；**扫描件（图片型）请先 OCR** 再上传；加密 PDF 需先解除密码 |
| `.docx` | ✅ | 完整保留标题层级、粗体/斜体、字号、对齐、列表、表格 |
| `.doc` | ❌ | 旧版二进制格式，请先用 Word 另存为 .docx |
| `.txt` / `.xls` / `.ppt` 等 | ❌ | 超出支持范围，上传时返回清晰错误提示 |

### 格式保留策略

- **Word/PDF → PDF**：翻译结果统一导出为 PDF。因 PDF 无结构化版式，采用**版式重建**策略——按内容结构（标题/段落/列表/表格）重新排版，保证内容完整与排版美观，非逐像素还原
- **专有名词处理**：在线翻译直接由翻译引擎处理（人名/地名/机构名本地化，如 Microsoft→微软、New York→纽约）；本地词典引擎对未收录专名做占位保护、翻译后还原

### 文档翻译 API

```text
POST /api/documents/translate   上传文档(multipart: file, source, target, use_online)
     -> {"task_id": "..."}
GET  /api/documents/status/<task_id>   轮询进度 {status, progress, message, error}
GET  /api/documents/download/<task_id>   下载翻译结果(PDF)
```

```bash
# curl 示例: 上传 PDF 翻译为中文并下载
curl -F "file=@report.pdf" -F "source=auto" -F "target=auto" \
     http://localhost:5000/api/documents/translate
```

## 四、接口文档

### `POST /api/translate`

```json
请求:
{
  "text": "Hello world",
  "source": "auto",        // auto | en | zh
  "target": "auto",        // auto | en | zh
  "use_online": true       // 可选, 是否使用在线增强
}

响应:
{
  "translation": "你好世界",
  "source": "en",
  "target": "zh",
  "engine": "online",      // online | local
  "coverage": 1.0,         // 本地词典覆盖率
  "uncovered": [],         // 未收录词
  "error": null,
  "warning": null
}
```

### `GET /api/health` — 健康检查

## 五、数据说明

- **数据源**：CC-CEDICT 开源中英词典（12 万余条），许可 CC BY-SA 4.0，详见 `translator/data/dictionary/README.md`
- **人工修正表**：`overrides.json` 精选高频词/常用短语的准确翻译，覆盖启发式反向索引的偏差
- **词形还原**：内置不规则动词表 + 规则后缀剥离，支持时态/复数/进行时查询

## 七、测试

```bash
# Python 单元测试 (54 个用例: 翻译引擎 23 + 文档处理 15 + 提效功能 14 + 其他)
python -m unittest tests.test_engine tests.test_docs tests.test_enhance -v

# 纯前端引擎测试 (Node)
node tests/test_js_engine.js
```

## 八、项目结构

```
english-translator/
├── run.py                  # 启动入口
├── config.py               # 全局配置(引擎/TM/术语表开关)
├── requirements.txt        # 依赖
├── Dockerfile              # 容器化部署
├── translator/
│   ├── core/               # 翻译核心
│   │   ├── engine.py       #   引擎主流程(含术语表/TM 接入)
│   │   ├── matcher.py      #   词典查询/词形还原
│   │   ├── tokenizer.py    #   中英文分词
│   │   ├── providers.py    #   多引擎提供商(MyMemory/DeepL/百度/腾讯/OpenAI)
│   │   ├── tm.py           #   翻译记忆(SQLite)
│   │   └── glossary.py     #   自定义术语表
│   ├── docs/               # 文档翻译
│   │   ├── block.py        #   结构化文本块模型(格式元数据)
│   │   ├── parser.py       #   PDF/DOCX 解析
│   │   ├── pipeline.py     #   分块翻译/专名保护/在线降级
│   │   ├── renderer.py     #   PDF 重建导出
│   │   └── tasks.py        #   后台任务管理
│   ├── data/               # 数据层
│   │   ├── loader.py       #   懒加载 + 单例缓存
│   │   └── dictionary/     #   词典索引 + 人工修正表
│   ├── web/                # Web 层
│   │   ├── api.py          #   Flask API(文本+文档+设置)
│   │   └── static/         #   用户界面(文本/文档双页签+设置弹窗)
│   └── utils/text.py       # 文本工具
├── scripts/                # 数据构建脚本
│   ├── build_dictionary.py #   CC-CEDICT -> 词典索引
│   └── build_js_demo.py    #   生成前端词典数据
├── static-demo/            # 纯前端演示版(可直接发布)
└── tests/                  # 单元测试
```
