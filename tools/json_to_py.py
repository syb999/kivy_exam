# tools/json_to_py.py
import json
import os
from glob import glob

def convert_jsons_to_py(json_dir='../assets/json', output_file='../data/questions.py'):
    """
    将指定目录下所有JSON文件合并为一个Python模块
    """
    # 创建数据字典
    questions_data = {}
    
    # 获取所有JSON文件
    json_files = glob(os.path.join(json_dir, '*.json'))
    
    if not json_files:
        raise ValueError(f"在目录 {json_dir} 中未找到JSON文件")
    
    # 读取并处理每个JSON文件
    for json_file in json_files:
        try:
            # 获取不带扩展名的文件名作为键名
            filename = os.path.basename(json_file)
            key_name = os.path.splitext(filename)[0]
            
            with open(json_file, 'r', encoding='utf-8') as f:
                # 将JSON内容存入字典
                questions_data[key_name] = json.load(f)
                
            print(f"成功加载: {filename} -> {key_name}")
        except Exception as e:
            print(f"加载文件 {json_file} 失败: {str(e)}")
            continue
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 写入Python模块
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 自动生成的题库数据模块\n")
        f.write("# 请不要手动修改此文件\n\n")
        f.write("questions = ")
        f.write(repr(questions_data))
        f.write("\n")
    
    print(f"成功生成Python模块: {output_file}")
    print(f"包含 {len(questions_data)} 个题库")

if __name__ == '__main__':
    convert_jsons_to_py()
