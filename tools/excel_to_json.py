
import pandas as pd
import json
import re

def is_empty_value(value):
    return pd.isna(value) or str(value).strip() in ('', 'nan')

def parse_options(option_str):
    if is_empty_value(option_str):
        return []
    option_str = str(option_str).strip()
    return [re.sub(r'^[A-Z]、', '', line).strip() 
            for line in option_str.split('\n') 
            if line.strip() and not is_empty_value(line)]

def parse_answer(answer_str, question_type):
    if is_empty_value(answer_str):
        return [] if question_type == 'multi' else ''
    
    answer = str(answer_str).strip()
    if question_type == 'judge':
        return 'A' if '正确' in answer else 'B'  # 直接返回字符串
    elif question_type == 'multi':
        return list(answer) if len(answer) > 1 else [answer]
    return answer[0] if answer else ''

def determine_question_type(row):
    if is_empty_value(row.get('题型')):
        return 'single'
    type_str = str(row['题型']).lower()
    if '多选' in type_str:
        return 'multi'
    elif '判断' in type_str:
        return 'judge'
    return 'single'

def convert_to_json_format(df):
    result = []
    for _, row in df.iterrows():
        if is_empty_value(row.get('题目')):
            continue
            
        question = {
            "type": determine_question_type(row),
            "question": str(row['题目']).strip(),
            "options": parse_options(row.get('选项')),
            "answer": parse_answer(row.get('答案'), determine_question_type(row)),
            "score": 10
        }
        result.append(question)
    return result

def excel_to_json(excel_path, json_path):
    try:
        df = pd.read_excel(excel_path, dtype='str').fillna('')
        json_data = convert_to_json_format(df)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"转换成功，共处理 {len(json_data)} 条数据")
    except Exception as e:
        print(f"转换失败: {str(e)}")

if __name__ == '__main__':
    excel_to_json('input.xlsx', 'output.json')

