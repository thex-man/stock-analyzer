import csv
import requests
import json
import os

def analyze_data_with_openrouter(input_csv_path, output_csv_path):
    """
    使用OpenRouter的API分析CSV，输出“作者-标题-观点”三列，且“观点”内换行显示（股票/逻辑分两行）。
    """
    # OpenRouter API密钥：从环境变量读取（务必保密，不要写入代码）
    # 设置方式：
    #   Windows: setx OPENROUTER_API_KEY "sk-or-v1-xxxx"
    #   Linux/macOS: export OPENROUTER_API_KEY="sk-or-v1-xxxx"
    API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    if not API_KEY:
        print("错误：请设置环境变量 OPENROUTER_API_KEY（不要写入代码！）")
        return

    # API基础配置
    API_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "mistralai/mistral-7b-instruct"  # 可替换为其他支持模型
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 检查输入文件
    if not os.path.exists(input_csv_path):
        print(f"错误：输入文件 {input_csv_path} 不存在！")
        return

    output_data = []  # 存储最终三列数据

    try:
        # 读取输入CSV并验证必要字段
        with open(input_csv_path, 'r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile)
            required_fields = ["作者", "标题", "完整内容"]
            missing_fields = [f for f in required_fields if f not in reader.fieldnames]
            if missing_fields:
                print(f"错误：输入CSV缺少字段：{', '.join(missing_fields)}")
                return
            data_to_analyze = [row for row in reader]

        if not data_to_analyze:
            print("输入CSV为空，无数据可分析！")
            return

        print(f"读取到 {len(data_to_analyze)} 条数据，开始分析（观点将换行显示）...\n")

        # 逐行分析
        for idx, row in enumerate(data_to_analyze, 1):
            # 提取基础信息（作者默认“未知”）
            author = row.get("作者", "未知作者").strip()
            title = row.get("标题", "无标题").strip()
            article_content = row.get("完整内容", "").strip()

            # 跳过无效内容
            if article_content in ["抓取失败", "抓取超时", "文章内容未找到", ""]:
                print(f"[{idx}/{len(data_to_analyze)}] 跳过无效内容：{title}")
                output_data.append({
                    "作者": author,
                    "标题": title,
                    "观点": "内容无效，无法分析"  # 无换行需求
                })
                continue

            print(f"[{idx}/{len(data_to_analyze)}] 分析中：{title}")

            # -------------------------- 关键修改：提示词要求换行 --------------------------
            prompt = f"""分析以下文章，严格按以下格式输出（必须换行，不超过100字）：
\n1. 推荐股票：xxx（无则写“无明确推荐股票”）
2. 推荐逻辑：xxx（核心催化/基本面，简洁明了）

文章内容：{article_content[:2000]}  # 截取前2000字避免API超限"""

            payload = {
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3  # 降低随机性，确保格式规范
            }

            try:
                # 调用API
                response = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=60)
                response.raise_for_status()

                # 提取带换行的分析结果
                result = response.json()
                analysis = result["choices"][0]["message"]["content"].strip()

                # 兜底：若模型未按格式输出，手动补充分隔
                if "1. 推荐股票：" not in analysis or "2. 推荐逻辑：" not in analysis:
                    analysis = "\n1. 推荐股票：无明确推荐股票\n2. 推荐逻辑：模型未返回有效分析"

                # 添加到输出数据（观点已含\n换行符）
                output_data.append({
                    "作者": author,
                    "标题": title,
                    "观点": analysis
                })
                print(f"[{idx}] 分析完成（已换行）：{title[:20]}...\n")

            except requests.exceptions.RequestException as e:
                error_msg = f"\n1. 推荐股票：无\n2. 推荐逻辑：API请求失败（{str(e)[:30]}...）"
                print(f"[{idx}] 分析失败：{error_msg}\n")
                output_data.append({"作者": author, "标题": title, "观点": error_msg})

    except Exception as e:
        print(f"文件处理错误：{str(e)}")
        return

    # -------------------------- 写入CSV：保留换行符 --------------------------
    try:
        output_fieldnames = ["作者", "标题", "观点"]
        # newline='' 确保CSV不自动添加多余空行，utf-8-sig兼容Excel中文显示
        with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
            writer.writeheader()
            writer.writerows(output_data)  # 直接写入含\n的观点，CSV会保留

        print(f"✅ 分析完成！")
        print(f"📁 结果文件：{os.path.abspath(output_csv_path)}")
        print(f"💡 查看提示：用Excel/WPS打开后，双击“观点”列单元格即可显示换行；或开启“自动换行”功能（Excel：开始→对齐方式→自动换行）")

    except Exception as e:
        print(f"写入CSV错误：{str(e)}")


if __name__ == "__main__":
    # 输入/输出文件路径（根据实际情况调整）
    INPUT_CSV = "jiuyangongshe_full_data.csv"  # 需含“作者”“标题”“完整内容”
    OUTPUT_CSV = "jiuyangongshe_analysis_linebreak.csv"  # 观点换行的输出文件

    analyze_data_with_openrouter(INPUT_CSV, OUTPUT_CSV)