# ==================== 統一新增作業流程管理器 ====================

import os
import datetime
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state, set_temp_task, get_temp_task, clear_temp_task,
    get_task_history, update_task_history, add_task
)
from firebase_admin import db
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, ApiClient, Configuration
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

class AddTaskFlowManager:
    """統一的新增作業流程管理器"""
    
    @staticmethod
    def start_add_task_flow(user_id, reply_token):
        """開始新增作業流程 - 統一入口"""
        set_user_state(user_id, "awaiting_task_name")
        clear_temp_task(user_id)
        
        # 獲取歷史記錄
        name_history, type_history, time_history = get_task_history(user_id)
        
        # 創建增強版作業名稱輸入介面
        bubble = AddTaskFlowManager._create_task_name_bubble(name_history)
        
        messages = [
            FlexMessage(
                alt_text="新增作業",
                contents=FlexContainer.from_dict(bubble)
            )
        ]

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )

    @staticmethod
    def _create_task_name_bubble(name_history):
        """創建作業名稱輸入卡片（只保留手動輸入＋最近歷史紀錄）"""
        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✨ 新增作業",
                        "color": "#FFFFFF",
                        "size": "xl",
                        "weight": "bold"
                    },
                    {
                        "type": "text",
                        "text": "開始記錄您的學習任務",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "margin": "sm"
                    }
                ],
                "backgroundColor": "#6366F1",
                "paddingAll": "20px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {
                        "type": "text",
                        "text": "請輸入作業名稱",
                        "size": "md",
                        "weight": "bold",
                        "color": "#1F2937"
                    },
                    {
                        "type": "text",
                        "text": "（可直接輸入，或點選最近使用）",
                        "size": "sm",
                        "color": "#6B7280",
                        "margin": "sm"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "💬 您也可以直接輸入作業名稱",
                        "size": "xs",
                        "color": "#6B7280",
                        "align": "center"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "❌ 取消",
                            "data": "cancel_add_task"
                        },
                        "style": "secondary",
                        "margin": "sm"
                    }
                ]
            }
        }

        # 歷史記錄（最多 3 筆）
        if name_history:
            history_buttons = []
            for name in name_history[-3:][::-1]:  # 取最近3筆，最新的排最上
                history_buttons.append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": f"📋 {name}",
                        "data": f"history_task_{name}"
                    },
                    "style": "secondary",
                    "height": "sm",
                    "margin": "sm"
                })
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

    @staticmethod
    def handle_task_name_selection(user_id, task_name, reply_token, is_quick=False):
        """處理作業名稱選擇（統一處理快速選擇和歷史記錄）"""
        temp_task = {"task": task_name}
        set_temp_task(user_id, temp_task)
        set_user_state(user_id, "awaiting_task_time")

        # 獲取時間歷史記錄
        _, _, time_history = get_task_history(user_id)
        
        # 創建增強版時間選擇介面
        bubble = AddTaskFlowManager._create_enhanced_time_bubble(time_history, user_id)

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="選擇預估時間",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def handle_manual_task_name_input(user_id, text, reply_token):
        """處理手動輸入作業名稱"""
        AddTaskFlowManager.handle_task_name_selection(user_id, text, reply_token)

    @staticmethod
    def _create_enhanced_time_bubble(time_history, user_id):
        """創建增強版時間選擇泡泡"""
        from collections import Counter
        
        # 分析歷史記錄，找出最常用的時間
        time_counter = Counter(time_history)
        most_common_time = time_counter.most_common(1)[0][0] if time_counter else "2小時"
        
        # 快速時間選項
        quick_times = [
            {"time": "0.5小時", "label": "30分鐘", "color": "#EC4899"},
            {"time": "1小時", "label": "1小時", "color": "#8B5CF6"},
            {"time": "1.5小時", "label": "1.5小時", "color": "#6366F1"},
            {"time": "2小時", "label": "2小時", "color": "#3B82F6"},
            {"time": "3小時", "label": "3小時", "color": "#10B981"},
            {"time": "4小時", "label": "4小時", "color": "#F59E0B"}
        ]
        
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
                    },
                    {
                        "type": "text",
                        "text": "幫助您更好地安排時間",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "margin": "sm"
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
                    }
                ]
            }
        }
        
        # 創建時間按鈕（3行2列）
        time_buttons_rows = [[] for _ in range(3)]  # 3 rows

        for i, time_option in enumerate(quick_times):
            is_recommended = time_option["time"] == most_common_time
            button = {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": f"{'⭐ ' if is_recommended else ''}{time_option['label']}",
                    "data": f"select_time_{time_option['time'].replace('小時', '')}"
                },
                "style": "primary" if is_recommended else "secondary",
                "color": time_option["color"] if is_recommended else None,
                "height": "sm",
                "flex": 1
            }
            row = i // 2  # 每2顆一排，共3排
            time_buttons_rows[row].append(button)

        # 補滿每行2顆
        for row in time_buttons_rows:
            while len(row) < 2:
                row.append({"type": "filler"})  # 填空讓每行對齊

        # 依序加進 bubble
        for row_buttons in time_buttons_rows:
            bubble["body"]["contents"].append({
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "margin": "sm",
                "contents": row_buttons
            })

        # 如果有不同的歷史記錄，加入其他常用時間
        unique_history = [t for t in time_history[-5:] if t not in [opt["time"] for opt in quick_times]]
        if unique_history:
            history_buttons = []
            for time in unique_history[:3]:
                history_buttons.append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": f"📊 {time}",
                        "data": f"select_time_{time.replace('小時', '')}"
                    },
                    "style": "secondary",
                    "height": "sm"
                })
            
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
        
        # Footer
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "💬 您也可以直接輸入時間（如：2.5小時）",
                    "size": "xs",
                    "color": "#6B7280",
                    "align": "center"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_add_task"
                    },
                    "style": "secondary",
                    "margin": "sm"
                }
            ]
        }
        
        return bubble

    @staticmethod
    def handle_time_selection(user_id, time_value, reply_token):
        """處理時間選擇"""
        temp_task = get_temp_task(user_id)
        if not temp_task:
            AddTaskFlowManager._send_error_and_restart(user_id, reply_token)
            return
            
        temp_task["estimated_time"] = float(time_value)
        set_temp_task(user_id, temp_task)
        set_user_state(user_id, "awaiting_task_type")

        # 獲取類型歷史記錄
        _, type_history, _ = get_task_history(user_id)
        
        # 創建增強版類型選擇介面
        bubble = AddTaskFlowManager._create_enhanced_type_bubble(type_history)

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="選擇作業類型",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def handle_manual_time_input(user_id, text, reply_token):
        """處理手動輸入時間"""
        try:
            hours = AddTaskFlowManager._parse_hours(text.strip())
            AddTaskFlowManager.handle_time_selection(user_id, str(hours), reply_token)
        except ValueError:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[
                            TextMessage(text="⚠️ 請輸入有效的時間格式\n例如：2、2.5、2小時、兩小時")
                        ]
                    )
                )

    @staticmethod
    def _create_enhanced_type_bubble(type_history):
        """創建增強版作業類型選擇泡泡"""
        # 定義常見類型及其配置
        type_configs = [
            {"name": "閱讀", "icon": "📖", "color": "#3B82F6", "desc": "閱讀理解、文獻閱讀"},
            {"name": "寫作", "icon": "✍️", "color": "#8B5CF6", "desc": "論文、報告撰寫"},
            {"name": "程式", "icon": "💻", "color": "#10B981", "desc": "程式設計、編碼"},
            {"name": "計算", "icon": "🧮", "color": "#F59E0B", "desc": "數學、統計計算"},
            {"name": "報告", "icon": "📊", "color": "#EF4444", "desc": "研究報告、簡報"},
            {"name": "實驗", "icon": "🔬", "color": "#06B6D4", "desc": "實驗操作、觀察"},
            {"name": "練習", "icon": "📝", "color": "#EC4899", "desc": "習題練習、複習"},
            {"name": "研究", "icon": "🔍", "color": "#84CC16", "desc": "資料蒐集、研究"}
        ]
        
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
                    },
                    {
                        "type": "text",
                        "text": "選擇類型幫助更好地管理學習",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "margin": "sm"
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
                        "type": "separator",
                        "margin": "lg"
                    },
                    {
                        "type": "text",
                        "text": "📋 常用類型",
                        "size": "sm",
                        "weight": "bold",
                        "color": "#4B5563"
                    }
                ]
            }
        }
        
        # 創建類型按鈕（4行2列，直式）
        type_buttons_rows = [[] for _ in range(4)]  # 4 rows

        for i, config in enumerate(type_configs):
            button = {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": f"{config['icon']} {config['name']}",
                    "data": f"select_type_{config['name']}"
                },
                "style": "secondary",
                "color": config["color"],
                "height": "sm",
                "flex": 1
            }
            row = i % 4  # 0~3，先直式一顆、再往下
            type_buttons_rows[row].append(button)

        # 補足每行2顆
        for row in type_buttons_rows:
            while len(row) < 2:
                row.append({"type": "filler"})  # 填空

        # 依序加入每行
        for row_buttons in type_buttons_rows:
            bubble["body"]["contents"].append({
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "margin": "sm",
                "contents": row_buttons
            })
  
        # 加入歷史記錄（如果有且不重複）
        unique_history = [t for t in type_history[-3:] if t not in [config["name"] for config in type_configs]]
        if unique_history:
            history_buttons = []
            for type_name in unique_history:
                history_buttons.append({
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": f"📋 {type_name}",
                        "data": f"select_type_{type_name}"
                    },
                    "style": "secondary",
                    "height": "sm"
                })
            
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
        
        # Footer
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "💬 您也可以直接輸入自訂類型",
                    "size": "xs",
                    "color": "#6B7280",
                    "align": "center"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_add_task"
                    },
                    "style": "secondary",
                    "margin": "sm"
                }
            ]
        }
        
        return bubble

    @staticmethod
    def handle_type_selection(user_id, type_value, reply_token):
        """處理類型選擇"""
        temp_task = get_temp_task(user_id)
        if not temp_task:
            AddTaskFlowManager._send_error_and_restart(user_id, reply_token)
            return
            
        temp_task["category"] = type_value
        set_temp_task(user_id, temp_task)
        set_user_state(user_id, "awaiting_task_due")

        # 創建增強版截止日期選擇介面
        bubble = AddTaskFlowManager._create_enhanced_due_bubble()

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="選擇截止日期",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def handle_manual_type_input(user_id, text, reply_token):
        """處理手動輸入類型"""
        AddTaskFlowManager.handle_type_selection(user_id, text.strip(), reply_token)

    @staticmethod
    def _create_enhanced_due_bubble():
        """創建增強版截止日期選擇泡泡"""
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        today = now.strftime("%Y-%m-%d")
        tomorrow = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        next_week = (now + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        next_month = (now + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        
        # 日期選項配置
        date_options = [
            {"label": "📌 今天", "date": today, "color": "#DC2626", "urgency": "high"},
            {"label": "📍 明天", "date": tomorrow, "color": "#F59E0B", "urgency": "medium"},
            {"label": "📎 一週後", "date": next_week, "color": "#3B82F6", "urgency": "normal"},
            {"label": "📅 一個月後", "date": next_month, "color": "#10B981", "urgency": "low"}
        ]

        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📅 截止日期",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold"
                    },
                    {
                        "type": "text",
                        "text": "設定截止日期幫助您管理進度",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "margin": "sm"
                    }
                ],
                "backgroundColor": "#F97316",
                "paddingAll": "15px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "請選擇截止日期",
                        "size": "md",
                        "weight": "bold",
                        "color": "#1F2937"
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
                    }
                ]
            }
        }
        
        # 創建日期按鈕
        date_buttons = []
        for option in date_options:
            # 計算距離天數
            try:
                due_date = datetime.datetime.strptime(option["date"], "%Y-%m-%d").date()
                today_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                days_diff = (due_date - today_date).days
                
                if days_diff == 0:
                    time_desc = "(今天)"
                elif days_diff == 1:
                    time_desc = "(明天)"
                elif days_diff <= 7:
                    time_desc = f"({days_diff}天後)"
                elif days_diff <= 30:
                    time_desc = f"({days_diff//7}週後)"
                else:
                    time_desc = f"({days_diff//30}月後)"
            except:
                time_desc = ""
            
            date_buttons.append({
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": f"{option['label']} {time_desc}",
                    "data": f"quick_due_{option['date']}"
                },
                "style": "secondary",
                "color": option["color"],
                "height": "sm"
            })
        
        bubble["body"]["contents"].extend([
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "margin": "sm",
                "contents": date_buttons
            },
            {
                "type": "separator",
                "margin": "lg"
            },
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "datetimepicker",
                            "label": "📅 選擇其他日期",
                            "data": "select_task_due",
                            "mode": "date",
                            "initial": today,
                            "max": "2099-12-31",
                            "min": today
                        },
                        "style": "primary",
                        "height": "sm"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🚫 不設定截止日期",
                            "data": "no_due_date"
                        },
                        "style": "secondary",
                        "height": "sm"
                    }
                ]
            }
        ])
        
        # Footer
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
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
        
        return bubble

    @staticmethod
    def handle_due_date_selection(user_id, due_date, reply_token):
        """處理截止日期選擇"""
        temp_task = get_temp_task(user_id)
        if not temp_task:
            AddTaskFlowManager._send_error_and_restart(user_id, reply_token)
            return
            
        temp_task["due"] = due_date
        set_temp_task(user_id, temp_task)
        
        # 顯示確認畫面
        AddTaskFlowManager._show_confirmation(user_id, reply_token)

    @staticmethod
    def handle_no_due_date(user_id, reply_token):
        """處理不設定截止日期"""
        temp_task = get_temp_task(user_id)
        if not temp_task:
            AddTaskFlowManager._send_error_and_restart(user_id, reply_token)
            return
        temp_task["due"] = "未設定"
        set_temp_task(user_id, temp_task)
        AddTaskFlowManager._show_confirmation(user_id, reply_token)

    @staticmethod
    def _show_confirmation(user_id, reply_token):
        """顯示確認新增作業畫面"""
        temp_task = get_temp_task(user_id)
        if not temp_task:
            AddTaskFlowManager._send_error_and_restart(user_id, reply_token)
            return

        # 創建確認卡片
        bubble = AddTaskFlowManager._create_confirmation_bubble(temp_task)

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="確認新增作業",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def _create_confirmation_bubble(temp_task):
        """創建確認新增作業卡片"""
        task_name = temp_task.get('task', '未設定')
        estimated_time = temp_task.get('estimated_time', 0)
        category = temp_task.get('category', '未設定')
        due_date = temp_task.get('due', '未設定')
        
        # 處理截止日期顯示
        due_display = due_date
        due_color = "#666666"
        if due_date != "未設定":
            try:
                due_datetime = datetime.datetime.strptime(due_date, "%Y-%m-%d")
                due_display = due_datetime.strftime("%Y年%m月%d日")
                
                # 計算距離天數並設定顏色
                now_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                days_diff = (due_datetime.date() - now_date).days
                
                if days_diff == 0:
                    due_display += " (今天)"
                    due_color = "#DC2626"
                elif days_diff == 1:
                    due_display += " (明天)"
                    due_color = "#F59E0B"
                elif days_diff <= 7:
                    due_display += f" ({days_diff}天後)"
                    due_color = "#3B82F6"
                else:
                    due_color = "#10B981"
            except:
                pass
        
        # 根據類型選擇圖示
        category_icons = {
            "閱讀": "📖", "寫作": "✍️", "程式": "💻", "計算": "🧮",
            "報告": "📊", "實驗": "🔬", "練習": "📝", "研究": "🔍"
        }
        category_icon = category_icons.get(category, "📋")
        
        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✅ 確認新增作業",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold"
                    },
                    {
                        "type": "text",
                        "text": "請檢查作業資訊是否正確",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "margin": "sm"
                    }
                ],
                "backgroundColor": "#6366F1",
                "paddingAll": "15px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📝", "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "作業名稱",
                                                "size": "sm",
                                                "color": "#6B7280"
                                            },
                                            {
                                                "type": "text",
                                                "text": task_name,
                                                "size": "md",
                                                "weight": "bold",
                                                "wrap": True,
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⏰", "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "預估時間",
                                                "size": "sm",
                                                "color": "#6B7280"
                                            },
                                            {
                                                "type": "text",
                                                "text": f"{estimated_time} 小時",
                                                "size": "md",
                                                "weight": "bold",
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": category_icon, "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "作業類型",
                                                "size": "sm",
                                                "color": "#6B7280"
                                            },
                                            {
                                                "type": "text",
                                                "text": category,
                                                "size": "md",
                                                "weight": "bold",
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📅", "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "截止日期",
                                                "size": "sm",
                                                "color": "#6B7280"
                                            },
                                            {
                                                "type": "text",
                                                "text": due_display,
                                                "size": "md",
                                                "weight": "bold",
                                                "color": due_color,
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "✅ 確認新增",
                            "data": "confirm_add_task"
                        },
                        "style": "primary",
                        "color": "#6366F1",
                        "flex": 2
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "❌ 取消",
                            "data": "cancel_add_task"
                        },
                        "style": "secondary",
                        "flex": 1
                    }
                ]
            }
        }
        
        return bubble

    @staticmethod
    def confirm_add_task(user_id, reply_token):
        """確認新增作業"""
        temp_task = get_temp_task(user_id)
        if not temp_task:
            reply = "⚠️ 發生錯誤，請重新開始新增作業流程"
        else:
            try:
                required_fields = ["task", "estimated_time", "category"]
                if any(f not in temp_task or temp_task[f] is None for f in required_fields):
                    reply = "⚠️ 缺少必要資訊，請重新開始新增作業流程"
                else:
                    # 確保時間格式正確
                    if isinstance(temp_task["estimated_time"], str):
                        temp_task["estimated_time"] = float(temp_task["estimated_time"])

                    # 更新歷史記錄
                    update_task_history(
                        user_id, 
                        temp_task["task"], 
                        temp_task["category"], 
                        temp_task["estimated_time"]
                    )

                    #確保截止日不為空字串/None
                    if "due" not in temp_task or not temp_task["due"] or temp_task["due"] == "None":
                        temp_task["due"] = "未設定"

                    # 新增作業
                    add_task(user_id, temp_task)
                    
                    # 記錄今天已新增作業（用於新增作業提醒）
                    today = datetime.datetime.now(
                        datetime.timezone(datetime.timedelta(hours=8))
                    ).strftime("%Y-%m-%d")
                    db.reference(f"users/{user_id}/last_add_task_date").set(today)
                    
                    # 清理暫存資料
                    clear_temp_task(user_id)
                    clear_user_state(user_id)
                    
                    # 成功訊息
                    reply = f"✅ 作業已成功新增！\n\n📝 {temp_task['task']}\n⏰ {temp_task['estimated_time']} 小時\n📚 {temp_task['category']}"
                    
            except Exception as e:
                print(f"新增作業失敗：{e}")
                reply = "❌ 發生錯誤，請稍後再試"

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token, 
                    messages=[TextMessage(text=reply)]
                )
            )

    @staticmethod
    def cancel_add_task(user_id, reply_token):
        """取消新增作業"""
        clear_temp_task(user_id)
        clear_user_state(user_id)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token, 
                    messages=[TextMessage(text="❌ 已取消新增作業")]
                )
            )

    @staticmethod
    def _send_error_and_restart(user_id, reply_token):
        """發送錯誤訊息並重啟流程"""
        clear_temp_task(user_id)
        clear_user_state(user_id)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 發生錯誤，請重新開始新增作業")]
                )
            )

    @staticmethod
    def _parse_hours(raw: str) -> float:
        """解析時間字串為小時數"""
        # 將全形數字轉半形
        trans = str.maketrans("０１２３４５６７８９．", "0123456789.")
        raw = raw.translate(trans)

        # 先找阿拉伯數字
        import re
        m = re.search(r"(\d+(?:\.\d+)?)", raw)
        if m:
            return float(m.group(1))

        # 處理中文數字
        zh_map = {
            "零":0, "一":1, "二":2, "兩":2, "三":3, "四":4, 
            "五":5, "六":6, "七":7, "八":8, "九":9, "十":10,
            "半":0.5, "個半":1.5, "點":0, "點五":0.5
        }
        
        # 處理 "一個半小時" 這類特殊情況
        if "個半" in raw:
            match = re.search(r"([一二三四五六七八九十]+)個半", raw)
            if match:
                num_str = match.group(1)
                base_num = zh_map.get(num_str, 0)
                return base_num + 0.5
        
        # 處理一般中文數字
        total = 0
        for ch in raw:
            if ch in zh_map:
                total += zh_map[ch]
        
        if total > 0:
            return float(total)

        # 仍然失敗就拋例外
        raise ValueError(f"無法解析時間：{raw}")
    
    @staticmethod
    def handle_natural_language_add_task(user_id, text, reply_token, task_info):
        """處理自然語言新增作業"""
        if not task_info or not task_info.get("task"):
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="❌ 無法從您的訊息中解析出作業資訊，請重新輸入或使用「新增作業」功能")]
                    )
                )
            return
        
        # 準備暫存資料
        temp_task = {
            "task": task_info.get("task"),
            "estimated_time": task_info.get("estimated_time"),
            "category": task_info.get("category"),
            "due": task_info.get("due")
        }
        
        # 獲取 AI 填寫的欄位
        ai_filled = task_info.get("ai_filled", [])
        
        #如果截止日是空，就填寫未設定
        if not temp_task.get("due"):
            temp_task["due"] = "未設定"

        # 如果有必要欄位未填寫，使用預設值
        if temp_task["estimated_time"] is None:
            temp_task["estimated_time"] = 2.0  # 預設 2 小時

        if temp_task["category"] is None:
            temp_task["category"] = "未分類"
        
        # 儲存暫存資料
        set_temp_task(user_id, temp_task)
        
        # 直接顯示確認畫面
        bubble = AddTaskFlowManager._create_natural_confirmation_bubble(temp_task, ai_filled)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="確認新增作業",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def _create_natural_confirmation_bubble(temp_task, ai_filled):
        """創建自然語言新增作業的確認卡片（已修正）"""
        task_name = temp_task.get('task', '未設定')
        estimated_time = temp_task.get('estimated_time', 0)
        category = temp_task.get('category', '未設定')
        due_date = temp_task.get('due', '未設定')

        # 處理截止日期顯示
        due_display = due_date
        due_color = "#666666"
        if due_date != "未設定":
            try:
                due_datetime = datetime.datetime.strptime(due_date, "%Y-%m-%d")
                due_display = due_datetime.strftime("%Y年%m月%d日")

                now_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
                days_diff = (due_datetime.date() - now_date).days

                if days_diff == 0:
                    due_display += " (今天)"
                    due_color = "#DC2626"
                elif days_diff == 1:
                    due_display += " (明天)"
                    due_color = "#F59E0B"
                elif days_diff <= 7:
                    due_display += f" ({days_diff}天後)"
                    due_color = "#3B82F6"
                else:
                    due_color = "#10B981"
            except:
                pass

        category_icons = {
            "閱讀": "📖", "寫作": "✍️", "程式": "💻", "計算": "🧮",
            "報告": "📊", "實驗": "🔬", "練習": "📝", "研究": "🔍"
        }
        category_icon = category_icons.get(category, "📋")

        # 動態建立 預估時間 標題列
        estimated_time_header_contents = [
            {
                "type": "text",
                "text": "預估時間",
                "size": "sm",
                "color": "#6B7280"
            }
        ]
        if "estimated_time" in ai_filled:
            estimated_time_header_contents.append({
                "type": "text",
                "text": "🤖 AI 預設",
                "size": "xs",
                "color": "#8B5CF6",
                "margin": "md"
            })

        # 動態建立 作業類型 標題列
        category_header_contents = [
            {
                "type": "text",
                "text": "作業類型",
                "size": "sm",
                "color": "#6B7280"
            }
        ]
        if "category" in ai_filled:
            category_header_contents.append({
                "type": "text",
                "text": "🤖 AI 推測",
                "size": "xs",
                "color": "#8B5CF6",
                "margin": "md"
            })

        # 動態建立 截止日期 標題列
        due_header_contents = [
            {
                "type": "text",
                "text": "截止日期",
                "size": "sm",
                "color": "#6B7280"
            }
        ]
        if "due" in ai_filled:
            due_header_contents.append({
                "type": "text",
                "text": "🤖 AI 預設",
                "size": "xs",
                "color": "#8B5CF6",
                "margin": "md"
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
                        "text": "🤖 AI 智慧解析",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold"
                    },
                    {
                        "type": "text",
                        "text": "請確認以下資訊是否正確",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "margin": "sm"
                    }
                ],
                "backgroundColor": "#8B5CF6",
                "paddingAll": "15px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📝", "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "text",
                                                "text": "作業名稱",
                                                "size": "sm",
                                                "color": "#6B7280"
                                            },
                                            {
                                                "type": "text",
                                                "text": task_name,
                                                "size": "md",
                                                "weight": "bold",
                                                "wrap": True,
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⏰", "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "box",
                                                "layout": "horizontal",
                                                "contents": estimated_time_header_contents # <-- 使用動態列表
                                            },
                                            {
                                                "type": "text",
                                                "text": f"{estimated_time} 小時",
                                                "size": "md",
                                                "weight": "bold",
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": category_icon, "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "box",
                                                "layout": "horizontal",
                                                "contents": category_header_contents # <-- 使用動態列表
                                            },
                                            {
                                                "type": "text",
                                                "text": category,
                                                "size": "md",
                                                "weight": "bold",
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {"type": "separator"},
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📅", "flex": 0, "size": "lg"},
                                    {
                                        "type": "box",
                                        "layout": "vertical",
                                        "flex": 1,
                                        "margin": "md",
                                        "contents": [
                                            {
                                                "type": "box",
                                                "layout": "horizontal",
                                                "contents": due_header_contents # <-- 使用動態列表
                                            },
                                            {
                                                "type": "text",
                                                "text": due_display,
                                                "size": "md",
                                                "weight": "bold",
                                                "color": due_color,
                                                "margin": "xs"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical", # <-- 外層使用垂直佈局
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "✅ 確認新增",
                            "data": "confirm_add_task"
                        },
                        "style": "primary",
                        "color": "#10B981"
                        # 這個按鈕會獨佔一行
                    },
                    {
                        "type": "box",
                        "layout": "horizontal", # <-- 內層使用水平佈局
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "✏️ 修改",
                                    "data": "add_task"
                                },
                                "style": "secondary",
                                "flex": 1 # <-- 讓這兩個按鈕平分寬度
                            },
                            {
                                "type": "button",
                                "action": {
                                    "type": "postback",
                                    "label": "❌ 取消",
                                    "data": "cancel_add_task"
                                },
                                "style": "secondary",
                                "flex": 1 # <-- 讓這兩個按鈕平分寬度
                            }
                        ]
                    }
                ]
            }
        }

        if ai_filled:
            bubble["body"]["contents"].append({
                "type": "text",
                "text": "💡 標記 🤖 的欄位由 AI 自動填寫",
                "size": "xs",
                "color": "#8B5CF6",
                "align": "center",
                "margin": "lg"
            })

        return bubble

# ==================== 更新後的處理器函數 ====================

def handle_add_task(user_id, reply_token):
    """新增作業 - 統一入口"""
    AddTaskFlowManager.start_add_task_flow(user_id, reply_token)

def handle_quick_task(data, user_id, reply_token):
    """處理快速選擇作業名稱"""
    task_name = data.replace("quick_task_", "")
    AddTaskFlowManager.handle_task_name_selection(user_id, task_name, reply_token, is_quick=True)

def handle_history_task(data, user_id, reply_token):
    """處理歷史作業名稱選擇"""
    task_name = data.replace("history_task_", "")
    AddTaskFlowManager.handle_task_name_selection(user_id, task_name, reply_token)

def handle_select_task_name(data, user_id, reply_token):
    """處理選擇作業名稱（保持兼容性）"""
    task_name = data.replace("select_task_name_", "")
    AddTaskFlowManager.handle_task_name_selection(user_id, task_name, reply_token)

def handle_select_time(data, user_id, reply_token):
    """處理時間選擇"""
    time_value = data.replace("select_time_", "")
    AddTaskFlowManager.handle_time_selection(user_id, time_value, reply_token)

def handle_select_type(data, user_id, reply_token):
    """處理類型選擇"""
    type_value = data.replace("select_type_", "")
    AddTaskFlowManager.handle_type_selection(user_id, type_value, reply_token)

def handle_quick_due(data, user_id, reply_token):
    """處理快速截止日期選擇"""
    due_date = data.replace("quick_due_", "")
    AddTaskFlowManager.handle_due_date_selection(user_id, due_date, reply_token)

def handle_select_task_due(event, user_id):
    """處理日期選擇器的截止日期"""
    date = event.postback.params.get("date", "")
    reply_token = event.reply_token
    
    if date:
        AddTaskFlowManager.handle_due_date_selection(user_id, date, reply_token)
    else:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 沒有取得日期，請重新選擇")]
                )
            )

def handle_no_due_date(user_id, reply_token):
    """處理不設定截止日期"""
    AddTaskFlowManager.handle_no_due_date(user_id, reply_token)

def handle_confirm_add_task(user_id, reply_token):
    """確認新增作業"""
    AddTaskFlowManager.confirm_add_task(user_id, reply_token)

def handle_cancel_add_task(user_id, reply_token):
    """取消新增作業"""
    AddTaskFlowManager.cancel_add_task(user_id, reply_token)

# ==================== 訊息處理器中的狀態處理 ====================

def handle_task_name_input(user_id: str, text: str, reply_token: str):
    """處理手動輸入作業名稱"""
    AddTaskFlowManager.handle_manual_task_name_input(user_id, text, reply_token)

def handle_estimated_time_input(user_id: str, text: str, reply_token: str):
    """處理手動輸入預估時間"""
    AddTaskFlowManager.handle_manual_time_input(user_id, text, reply_token)

def handle_task_type_input(user_id: str, text: str, reply_token: str):
    """處理手動輸入作業類型"""
    AddTaskFlowManager.handle_manual_type_input(user_id, text, reply_token)