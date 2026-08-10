# 数据来源与许可说明

本目录下的词典数据 (`zh_en.json`, `en_zh.json`) 由 **CC-CEDICT** 开源词典构建而来。

## 数据源信息

- **名称**: CC-CEDICT (Community-maintained Chinese-English Dictionary)
- **维护方**: MDBG (https://www.mdbg.net)
- **官方页面**: https://www.mdbg.net/chinese/dictionary?page=cc-cedict
- **原始文件**: `cedict_1_0_ts_utf-8_mdbg.txt.gz`
- **词条规模**: 12 万余条中英双语词条
- **内容**: 简体/繁体中文、拼音、英文释义

## 许可证

原始数据遵循 **Creative Commons Attribution-ShareAlike 4.0 International License** (CC BY-SA 4.0)

- 许可证全文: https://creativecommons.org/licenses/by-sa/4.0/
- 依据该许可证要求，本项目对数据进行了格式转换与索引构建（属演绎作品），
  使用本项目及数据时请保留本说明并注明出处为 CC-CEDICT / MDBG。

## 构建方式

运行以下命令可自行从原始数据重建本目录索引：

```bash
# 1. 下载原始数据 (约 4MB)
curl -o cedict.txt.gz https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz

# 2. 构建索引
python scripts/build_dictionary.py cedict.txt.gz translator/data/dictionary
```
