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
        start_time = datetime.datetime.strptime(start, "%H:%M")
        end_time = datetime.datetime.strptime(end, "%H:%M")
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

def make_timetable_card(blocks, total_hours):
    """
    製作時間表卡片，使用簡潔的表格格式
    """
    if not blocks:
        return None

    rows = []
    for block in blocks:
        time_range = f"{block['start']} ~ {block['end']}"
        task_text = block['task']
        emoji = block.get('emoji', EMOJI_MAP['default'])
        
        # 組合任務文字，只顯示時間和任務名稱
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

def make_schedule_card(task):
    name = task.get("task", "未命名")
    category = task.get("category", "未分類")
    time = task.get("estimated_time", "未知")
    due = task.get("due", "未設定")
    icon = "📝" if "寫" in category else "📚" if "讀" in category else "💻" if "程式" in category else "✅"

    bubble = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": f"{icon} {name}", "weight": "bold", "size": "lg", "wrap": True},
                {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                    {"type": "text", "text": "⏰ 時間：", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": f"{time} 小時", "size": "sm", "color": "#111111"}
                ]},
                {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                    {"type": "text", "text": "📅 截止：", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": due, "size": "sm", "color": "#111111"}
                ]},
                {"type": "box", "layout": "baseline", "spacing": "sm", "contents": [
                    {"type": "text", "text": "📚 類別：", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": category, "size": "sm", "color": "#111111"}
                ]}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {"type": "button", "style": "primary", "color": "#4CAF50", "action": {"type": "postback", "label": "✅ 完成", "data": f"done_{name}"}},
                {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "⏰ 延後", "data": f"delay_{name}"}},
                {"type": "button", "style": "secondary", "action": {"type": "postback", "label": "🗑 刪除", "data": f"delete_{name}"}}
            ]
        }
    }
    return bubble


def make_schedule_carousel(tasks):
    bubbles = []
    for task in tasks[:10]:
        name = task.get("task", "未命名")
        due = task.get("due", "未設定")

        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": f"📘 {name}", "weight": "bold", "size": "md", "wrap": True},
                    {"type": "text", "text": f"📅 截止：{due}", "size": "sm", "color": "#888888"}
                ]
            }
        }

        bubbles.append(bubble)

    return {
        "type": "carousel",
        "contents": bubbles
    }

def make_weekly_progress_card(completed_tasks, total_hours, avg_hours_per_day):
    """
    製作週進度卡片
    """
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "📊 本週進度",
                    "weight": "bold",
                    "size": "lg"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"✅ 已完成任務：{completed_tasks} 項",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": f"⏱️ 總工作時數：{total_hours} 小時",
                            "size": "md"
                        },
                        {
                            "type": "text",
                            "text": f"📈 平均每日：{avg_hours_per_day:.1f} 小時",
                            "size": "md"
                        }
                    ]
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
        time_range = f"{block['start']} - {block['end']}"
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
                    "flex": 1,  # 改為 flex: 1 讓時間佔一半
                    "contents": [
                        {
                            "type": "text",
                            "text": time_range,
                            "size": "sm",  # 改為 sm 讓字體稍大
                            "color": "#666666",
                            "weight": "bold",
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
                    "flex": 1,  # 作業部分也佔一半
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
                                    "align": "center"  # 新增置中對齊
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
                            "color": "#FFFFFF"  # 透明分隔線
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