import re
import datetime
from typing import List, Dict, Any

# 常數定義
TIME_RANGE_PATTERN = r'\d+\.\s*([^\s]+)?\s*(\d{1,2}:\d{2})\s*[~-]\s*(\d{1,2}:\d{2})\s*[｜|]\s*(.*?)(?:\s*[（(](\d+)分鐘[）)])?$'
EMOJI_MAP = {
    'default': '🕘',
    'meal': '🥪',
    'study': '📖',
    'rest': '🧠',
    'coding': '💻',
    'writing': '✍️',
    'reading': '📚',
    'exercise': '🏃',
    'meeting': '👥'
}

def normalize_time(time_str):
    """
    標準化時間格式，處理超過 24:00 的情況
    例如：25:30 -> 01:30 (隔天)
    """
    try:
        parts = time_str.split(':')
        if len(parts) != 2:
            return time_str
            
        hours = int(parts[0])
        minutes = int(parts[1])
        
        # 處理超過 24 小時的情況
        if hours >= 24:
            hours = hours % 24
            # 可以在這裡加上 (隔天) 的標記
            return f"{hours:02d}:{minutes:02d}"
        
        return time_str
    except:
        return time_str

def make_enhanced_time_bubble(time_history: List[str], user_id: str) -> Dict[str, Any]:
    """
    增強版時間選擇泡泡，包含快速選項和智慧建議
    """
    # 分析歷史記錄，找出最常用的時間
    from collections import Counter
    time_counter = Counter(time_history)
    most_common_time = time_counter.most_common(1)[0][0] if time_counter else "2小時"
    
    # 快速時間選項
    quick_times = ["0.5小時", "1小時", "1.5小時", "2小時", "3小時"]
    quick_buttons = []
    
    for time in quick_times:
        color = "#10B981" if time == most_common_time else "#6B7280"
        quick_buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"⏱️ {time}",
                "data": f"select_time_{time.replace('小時', '')}"
            },
            "style": "secondary",
            "color": color
        })
    
    # 歷史記錄按鈕（去重）
    unique_history = list(dict.fromkeys(time_history[-5:]))  # 保留最近5個不重複的
    history_buttons = []
    
    for time in unique_history[:3]:
        if time not in quick_times:  # 避免重複
            history_buttons.append({
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": f"📊 {time}",
                    "data": f"select_time_{time.replace('小時', '')}"
                },
                "style": "secondary"
            })
    
    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "⏰ 預估完成時間",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "weight": "bold"
                }
            ],
            "backgroundColor": "#EC4899",
            "paddingAll": "15px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇或輸入預估時間",
                    "size": "md",
                    "weight": "bold",
                    "color": "#1F2937"
                },
                {
                    "type": "text",
                    "text": f"💡 根據您的習慣，建議：{most_common_time}",
                    "size": "sm",
                    "color": "#059669",
                    "wrap": True,
                    "margin": "sm"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "text",
                    "text": "⚡ 快速選擇",
                    "size": "sm",
                    "weight": "bold",
                    "color": "#4B5563"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "sm",
                    "contents": quick_buttons[:3]  # 第一行顯示3個
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "sm",
                    "contents": quick_buttons[3:]  # 第二行顯示剩餘的
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_add_task"
                    },
                    "style": "secondary"
                }
            ]
        }
    }
    
    # 如果有不同的歷史記錄，加入
    if history_buttons:
        bubble["body"]["contents"].extend([
            {
                "type": "separator",
                "margin": "lg"
            },
            {
                "type": "text",
                "text": "📋 其他常用時間",
                "size": "sm",
                "weight": "bold",
                "color": "#4B5563",
                "margin": "md"
            },
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "margin": "sm",
                "contents": history_buttons
            }
        ])
    
    return bubble

def make_enhanced_type_bubble(type_history: List[str]) -> Dict[str, Any]:
    """
    增強版作業類型選擇泡泡
    """
    # 定義常見類型及其圖示和顏色
    type_config = {
        "閱讀": {"icon": "📖", "color": "#3B82F6"},
        "寫作": {"icon": "✍️", "color": "#8B5CF6"},
        "程式": {"icon": "💻", "color": "#10B981"},
        "計算": {"icon": "🧮", "color": "#F59E0B"},
        "報告": {"icon": "📊", "color": "#EF4444"},
        "研究": {"icon": "🔬", "color": "#06B6D4"},
        "練習": {"icon": "📝", "color": "#EC4899"},
        "其他": {"icon": "📋", "color": "#6B7280"}
    }
    
    # 常用類型按鈕
    common_types = ["閱讀", "寫作", "程式", "計算", "報告", "練習"]
    type_buttons = []
    
    for type_name in common_types:
        config = type_config.get(type_name, type_config["其他"])
        type_buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"{config['icon']} {type_name}",
                "data": f"select_type_{type_name}"
            },
            "style": "secondary",
            "color": config["color"]
        })
    
    # 歷史記錄按鈕
    history_buttons = []
    unique_history = list(dict.fromkeys(type_history[-5:]))
    
    for type_name in unique_history[:3]:
        if type_name not in common_types:
            config = type_config.get(type_name, type_config["其他"])
            history_buttons.append({
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": f"{config['icon']} {type_name}",
                    "data": f"select_type_{type_name}"
                },
                "style": "secondary"
            })
    
    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📚 作業類型",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "weight": "bold"
                }
            ],
            "backgroundColor": "#7C3AED",
            "paddingAll": "15px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇作業類型",
                    "size": "md",
                    "weight": "bold",
                    "color": "#1F2937"
                },
                {
                    "type": "text",
                    "text": "這有助於安排您的學習時間",
                    "size": "sm",
                    "color": "#6B7280",
                    "wrap": True
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": type_buttons[:3]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "sm",
                    "contents": type_buttons[3:6]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_add_task"
                    },
                    "style": "secondary"
                }
            ]
        }
    }
    
    # 加入歷史記錄
    if history_buttons:
        bubble["body"]["contents"].extend([
            {
                "type": "separator",
                "margin": "lg"
            },
            {
                "type": "text",
                "text": "📋 最近使用",
                "size": "sm",
                "weight": "bold",
                "color": "#4B5563",
                "margin": "md"
            },
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "margin": "sm",
                "contents": history_buttons
            }
        ])
    
    return bubble

def calculate_duration(start, end):
    """
    計算時間區間的持續時間（分鐘）
    """
    try:
        # 先標準化時間
        start = normalize_time(start)
        end = normalize_time(end)
        
        start_time = datetime.datetime.strptime(start, "%H:%M")
        end_time = datetime.datetime.strptime(end, "%H:%M")
        
        # 如果結束時間小於開始時間，表示跨日
        if end_time < start_time:
            # 加上一天的時間
            end_time += datetime.timedelta(days=1)
        
        return int((end_time - start_time).total_seconds() / 60)
    except:
        return 0

def extract_schedule_blocks(text):
    """
    從 Gemini 回傳文字中擷取時間表內容
    支援格式：
    1. 🕘 09:00 ~ 12:30｜快點完成（210 分鐘）
    2. 🥪 12:30 ~ 13:00｜午餐（30 分鐘）
    3. 📖 13:00 ~ 14:00｜作業系統｜閱讀
    """
    blocks = []
    
    # 調試訊息
    print("開始解析排程文字：", text)
    
    # 先將文字按行分割
    lines = text.strip().split('\n')
    
    for line in lines:
        # 跳過空行
        if not line.strip():
            continue
            
        # 匹配新格式
        pattern = re.compile(TIME_RANGE_PATTERN)
        match = pattern.search(line)
        
        if match:
            emoji, start, end, task, duration = match.groups()
            
            # 標準化時間
            start = normalize_time(start)
            end = normalize_time(end)
            
            # 檢查任務是否包含類別
            task_parts = task.split('｜')
            task_name = task_parts[0].strip()
            category = task_parts[1].strip() if len(task_parts) > 1 else "未分類"
            
            # 如果沒有找到時長，計算時長
            if not duration:
                duration = str(calculate_duration(start, end))
            
            blocks.append({
                'start': start,
                'end': end,
                'task': task_name,
                'duration': f"{duration}分鐘",
                'category': category,
                'emoji': emoji if emoji else EMOJI_MAP['default']
            })
            continue
            
        # 如果沒有匹配到新格式，嘗試更簡單的格式
        pattern_simple = re.compile(r'\d+\.\s*(\d{1,2}:\d{2})\s*[~-]\s*(\d{1,2}:\d{2})\s*[｜|]\s*(.*?)(?:\s*[（(](\d+)分鐘[）)])?$')
        match_simple = pattern_simple.search(line)
        
        if match_simple:
            start, end, task, duration = match_simple.groups()
            
            # 標準化時間
            start = normalize_time(start)
            end = normalize_time(end)
            
            # 計算時長
            if not duration:
                duration = str(calculate_duration(start, end))
            
            blocks.append({
                'start': start,
                'end': end,
                'task': task.strip(),
                'duration': f"{duration}分鐘",
                'category': "未分類",
                'emoji': EMOJI_MAP['default']
            })
    
    print("解析結果：", blocks)
    return blocks

def format_time_range(start, end):
    """
    格式化時間範圍，處理跨日情況
    """
    start_normalized = normalize_time(start)
    end_normalized = normalize_time(end)
    
    # 檢查是否跨日
    try:
        start_hour = int(start.split(':')[0])
        end_hour = int(end.split(':')[0])
        
        # 如果原始結束時間 >= 24 或結束時間 < 開始時間，表示跨日
        if int(end.split(':')[0]) >= 24 or (end_hour < start_hour and start_hour < 24):
            return f"{start_normalized} ~ {end_normalized}(隔天)"
        else:
            return f"{start_normalized} ~ {end_normalized}"
    except:
        return f"{start_normalized} ~ {end_normalized}"

def make_timetable_card(blocks, total_hours):
    """
    製作時間表卡片，使用簡潔的表格格式
    """
    if not blocks:
        return None

    rows = []
    for block in blocks:
        time_range = format_time_range(block['start'], block['end'])
        task_text = block['task']
        emoji = block.get('emoji', EMOJI_MAP['default'])
        
        # 組合任務文字
        task_display = f"{emoji} {time_range}｜{task_text}"

        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": task_display,
                    "size": "sm",
                    "wrap": True,
                    "color": "#111111"
                }
            ]
        })

    # 添加總時數資訊
    total_hours_text = f"✅ 今日總時長：{total_hours} 小時"
    if total_hours > 7:
        total_hours_text += "\n⚠️ 今天安排較滿，建議保留喘息時間"

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "📅 今日排程",
                    "weight": "bold",
                    "size": "md"
                },
                {"type": "separator"},
                *rows,
                {
                    "type": "text",
                    "text": total_hours_text,
                    "size": "sm",
                    "color": "#666666",
                    "margin": "md"
                }
            ]
        }
    }
    return bubble

def make_optimized_schedule_card(blocks, total_hours, available_hours, pending_tasks):
    """製作優化的排程卡片"""
    if not blocks:
        return None
    
    # 計算完成率
    scheduled_task_count = len([b for b in blocks if b['task'] not in ['短暫休息', '午餐', '晚餐']])
    completion_rate = min(100, int((scheduled_task_count / len(pending_tasks)) * 100))
    
    # 時間利用率
    utilization_rate = min(100, int((total_hours / available_hours) * 100))
    
    # 建立時間軸視覺化
    timeline_contents = []
    for i, block in enumerate(blocks):
        time_range = format_time_range(block['start'], block['end'])
        emoji = block.get('emoji', '📌')
        task_name = block['task']
        category = block.get('category', '')
        
        # 判斷任務類型的顏色
        if '休息' in task_name or '午餐' in task_name:
            bg_color = "#E8F5E9"
            text_color = "#4CAF50"
        elif category == "緊急":
            bg_color = "#FFEBEE"
            text_color = "#F44336"
        else:
            bg_color = "#E3F2FD"
            text_color = "#2196F3"
        
        timeline_contents.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "md",
            "margin": "md" if i > 0 else "none",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "contents": [
                        {
                            "type": "text",
                            "text": time_range,
                            "size": "sm",
                            "color": "#666666",
                            "weight": "bold",
                            "align": "center",
                            "wrap": True
                        }
                    ]
                },
                {
                    "type": "separator",
                    "color": "#EEEEEE"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "backgroundColor": bg_color,
                            "cornerRadius": "8px",
                            "paddingAll": "10px",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"{emoji} {task_name}",
                                    "size": "sm",
                                    "color": text_color,
                                    "weight": "bold",
                                    "wrap": True,
                                    "align": "center"
                                }
                            ]
                        }
                    ]
                }
            ]
        })
    
    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📅 今日最佳排程",
                    "color": "#FFFFFF",
                    "size": "xl",
                    "weight": "bold"
                },
                {
                    "type": "text",
                    "text": f"為您安排了 {total_hours} 小時的學習計畫",
                    "color": "#FFFFFF",
                    "size": "sm",
                    "margin": "sm"
                }
            ],
            "backgroundColor": "#FF6B6B",
            "paddingAll": "20px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "lg",
            "contents": [
                # 統計資訊
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"{utilization_rate}%",
                                    "size": "xl",
                                    "weight": "bold",
                                    "align": "center",
                                    "color": "#FF6B6B"
                                },
                                {
                                    "type": "text",
                                    "text": "時間利用率",
                                    "size": "xs",
                                    "color": "#666666",
                                    "align": "center"
                                }
                            ]
                        },
                        {
                            "type": "separator",
                            "color": "#EEEEEE"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"{scheduled_task_count}/{len(pending_tasks)}",
                                    "size": "xl",
                                    "weight": "bold",
                                    "align": "center",
                                    "color": "#4CAF50"
                                },
                                {
                                    "type": "text",
                                    "text": "任務安排",
                                    "size": "xs",
                                    "color": "#666666",
                                    "align": "center"
                                }
                            ]
                        }
                    ]
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                # 時間軸標題
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "⏰ 時間安排",
                                    "size": "md",
                                    "weight": "bold",
                                    "color": "#333333",
                                    "align": "center"
                                }
                            ]
                        },
                        {
                            "type": "separator",
                            "color": "#FFFFFF"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "📚 作業項目",
                                    "size": "md",
                                    "weight": "bold",
                                    "color": "#333333",
                                    "align": "center"
                                }
                            ]
                        }
                    ]
                },
                {
                    "type": "separator",
                    "margin": "sm"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": timeline_contents
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "📋 查看作業列表",
                        "data": "view_tasks"
                    },
                    "style": "primary",
                    "color": "#FF6B6B"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "⏰ 重新安排時間",
                        "data": "show_schedule"
                    },
                    "style": "secondary"
                }
            ]
        }
    }
    
    # 如果有未安排的任務，添加提醒
    if scheduled_task_count < len(pending_tasks):
        bubble["body"]["contents"].append({
            "type": "box",
            "layout": "vertical",
            "margin": "lg",
            "backgroundColor": "#FFF9C4",
            "cornerRadius": "8px",
            "paddingAll": "10px",
            "contents": [
                {
                    "type": "text",
                    "text": f"💡 還有 {len(pending_tasks) - scheduled_task_count} 個任務未安排",
                    "size": "sm",
                    "color": "#F57C00",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": "建議增加可用時間或延後部分任務",
                    "size": "xs",
                    "color": "#666666",
                    "margin": "sm",
                    "wrap": True
                }
            ]
        })
    
    return bubble

def parse_schedule_response(raw_text):
    """
    解析排程回應
    """
    print("原始回應：", raw_text)
    
    # 檢查是否包含排程標記
    if "📅 今日排程" in raw_text:
        parts = raw_text.split("📅 今日排程")
        explanation = parts[0].strip()
        schedule_text = "📅 今日排程" + parts[1].strip()
        
        # 從排程文字中提取總時數
        total_hours_match = re.search(r'✅ 今日總時長：(\d+(?:\.\d+)?)', raw_text)
        total_hours = float(total_hours_match.group(1)) if total_hours_match else 0
    else:
        # 如果沒有標記，嘗試直接解析
        lines = raw_text.strip().split('\n')
        schedule_lines = []
        explanation_lines = []
        
        for line in lines:
            if re.match(r'\d+\.\s*[^\s]+', line):
                schedule_lines.append(line)
            else:
                explanation_lines.append(line)
        
        explanation = '\n'.join(explanation_lines).strip()
        schedule_text = '\n'.join(schedule_lines).strip()
        
        # 計算總時數
        blocks = extract_schedule_blocks(schedule_text)
        total_hours = sum(float(block['duration'].replace('分鐘', '')) / 60 for block in blocks)

    return explanation, schedule_text, total_hours

def validate_schedule_time(blocks, available_hours):
    """
    驗證排程是否超過可用時間
    """
    if not blocks:
        return True, 0
    
    total_minutes = 0
    for block in blocks:
        try:
            duration_str = block.get('duration', '0分鐘')
            minutes = int(duration_str.replace('分鐘', ''))
            total_minutes += minutes
        except:
            pass
    
    total_hours = total_minutes / 60
    is_valid = total_hours <= available_hours
    
    return is_valid, total_hours