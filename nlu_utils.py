import re
from datetime import datetime, timedelta
import jieba
import jieba.posseg as pseg

# 預設的任務分類
DEFAULT_CATEGORIES = ['作業', '考試', '報告', '專案', '其他']

def parse_task_from_text(text: str) -> dict:
    """
    從自然語言文本中解析任務資訊
    
    Args:
        text (str): 使用者輸入的自然語言文本
        
    Returns:
        dict: 包含解析出的任務資訊，格式為：
        {
            'task': str or None,  # 任務名稱
            'estimated_time': float or None,  # 預估時間（小時）
            'due': str or None,  # 截止日期 (YYYY-MM-DD)
            'category': str or None  # 任務分類
        }
    """
    result = {
        'task': None,
        'estimated_time': None,
        'due': None,
        'category': None
    }
    
    # 使用結巴分詞進行詞性標註
    words = pseg.cut(text)
    
    # 解析任務名稱
    task_parts = []
    for word, flag in words:
        # 排除日期、時間、數字等詞
        if not (flag.startswith('t') or flag.startswith('m')):
            task_parts.append(word)
    if task_parts:
        result['task'] = ''.join(task_parts).strip()
    
    # 解析預估時間
    time_patterns = [
        (r'(\d+(?:\.\d+)?)\s*小時', 1),  # 例如：2.5小時
        (r'(\d+)\s*分鐘', lambda x: float(x)/60),  # 例如：30分鐘
        (r'(\d+)\s*分', lambda x: float(x)/60),  # 例如：30分
    ]
    
    for pattern, multiplier in time_patterns:
        match = re.search(pattern, text)
        if match:
            time_value = float(match.group(1))
            if callable(multiplier):
                time_value = multiplier(time_value)
            else:
                time_value *= multiplier
            result['estimated_time'] = time_value
            break
    
    # 解析截止日期
    today = datetime.now()
    date_patterns = {
        r'明天': lambda: today + timedelta(days=1),
        r'後天': lambda: today + timedelta(days=2),
        r'大後天': lambda: today + timedelta(days=3),
        r'下週一': lambda: today + timedelta(days=(7-today.weekday())%7+1),
        r'下週二': lambda: today + timedelta(days=(7-today.weekday())%7+2),
        r'下週三': lambda: today + timedelta(days=(7-today.weekday())%7+3),
        r'下週四': lambda: today + timedelta(days=(7-today.weekday())%7+4),
        r'下週五': lambda: today + timedelta(days=(7-today.weekday())%7+5),
        r'下週六': lambda: today + timedelta(days=(7-today.weekday())%7+6),
        r'下週日': lambda: today + timedelta(days=(7-today.weekday())%7+7),
        r'(\d{4})年(\d{1,2})月(\d{1,2})日': lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
        r'(\d{1,2})月(\d{1,2})日': lambda m: datetime(today.year, int(m.group(1)), int(m.group(2))),
    }
    
    for pattern, date_func in date_patterns.items():
        match = re.search(pattern, text)
        if match:
            if callable(date_func):
                try:
                    date = date_func(match)
                except:
                    date = date_func()
            else:
                date = date_func()
            result['due'] = date.strftime('%Y-%m-%d')
            break
    
    # 解析分類
    category_pattern = r'分類[是為]([^，。,.]+)'
    match = re.search(category_pattern, text)
    if match:
        category = match.group(1).strip()
        if category in DEFAULT_CATEGORIES:
            result['category'] = category
    
    return result

def is_task_description(text: str) -> bool:
    """
    判斷文本是否可能是任務描述
    
    Args:
        text (str): 使用者輸入的文本
        
    Returns:
        bool: 是否可能是任務描述
    """
    # 檢查是否包含常見的任務相關關鍵詞
    task_keywords = ['完成', '做', '寫', '準備', '繳交', '提交', '報告', '作業', '考試']
    
    # 檢查是否包含時間相關詞彙
    time_keywords = ['小時', '分鐘', '明天', '後天', '下週', '月', '日']
    
    # 檢查是否包含分類相關詞彙
    category_keywords = ['分類', '類別']
    
    # 如果文本太短，可能不是任務描述
    if len(text) < 4:
        return False
    
    # 檢查是否包含任務關鍵詞
    has_task_keyword = any(keyword in text for keyword in task_keywords)
    
    # 檢查是否包含時間相關詞彙
    has_time_keyword = any(keyword in text for keyword in time_keywords)
    
    # 檢查是否包含分類相關詞彙
    has_category_keyword = any(keyword in text for keyword in category_keywords)
    
    # 如果包含任務關鍵詞，且至少包含時間或分類關鍵詞之一，則可能是任務描述
    return has_task_keyword and (has_time_keyword or has_category_keyword) 