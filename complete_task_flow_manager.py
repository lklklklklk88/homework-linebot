# ==================== 統一完成作業流程管理器 ====================

import os
import datetime
from firebase_utils import (
    load_data, save_data, set_user_state, get_user_state,
    clear_user_state
)
from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, ApiClient, Configuration
from linebot.v3.messaging.models import TextMessage, FlexMessage, FlexContainer

configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

class CompleteTaskFlowManager:
    """統一的完成作業流程管理器"""
    
    @staticmethod
    def start_complete_task_flow(user_id, reply_token):
        """開始完成作業流程 - 統一入口"""
        tasks = load_data(user_id)
        
        # 過濾出未完成的作業
        incomplete_tasks = [task for task in tasks if not task.get("done", False)]
        
        if not incomplete_tasks:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="✅ 太棒了！目前沒有未完成的作業")]
                    )
                )
            return
        
        # 創建增強版完成作業選擇介面
        bubble = CompleteTaskFlowManager._create_task_selection_bubble(incomplete_tasks)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="選擇要完成的作業",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def _create_task_selection_bubble(incomplete_tasks):
        """創建作業選擇卡片"""
        # 計算統計資訊
        total_count = len(incomplete_tasks)
        today_count = 0
        urgent_count = 0
        
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        today = now.date()
        
        for task in incomplete_tasks:
            due = task.get("due", "未設定")
            if due != "未設定":
                try:
                    due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                    if due_date == today:
                        today_count += 1
                    elif due_date < today:
                        urgent_count += 1
                except:
                    pass
        
        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "✅ 完成作業",
                        "color": "#FFFFFF",
                        "size": "xl",
                        "weight": "bold"
                    },
                    {
                        "type": "text",
                        "text": "選擇已完成的作業",
                        "color": "#FFFFFF",
                        "size": "sm",
                        "margin": "sm"
                    }
                ],
                "backgroundColor": "#10B981",
                "paddingAll": "20px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": []
            }
        }
        
        # 添加統計資訊
        if urgent_count > 0 or today_count > 0:
            stats_contents = []
            if urgent_count > 0:
                stats_contents.append({
                    "type": "text",
                    "text": f"🔥 {urgent_count} 項已過期",
                    "size": "sm",
                    "color": "#DC2626",
                    "weight": "bold"
                })
            if today_count > 0:
                stats_contents.append({
                    "type": "text",
                    "text": f"⏰ {today_count} 項今天到期",
                    "size": "sm",
                    "color": "#F59E0B",
                    "weight": "bold"
                })
            
            bubble["body"]["contents"].extend([
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "md",
                    "contents": stats_contents
                },
                {
                    "type": "separator",
                    "margin": "md"
                }
            ])
        
        # 將作業分類
        overdue_tasks = []
        today_tasks = []
        upcoming_tasks = []
        no_due_tasks = []
        
        for i, task in enumerate(incomplete_tasks):
            task_with_index = {"index": i, "task": task}
            due = task.get("due", "未設定")
            
            if due == "未設定":
                no_due_tasks.append(task_with_index)
            else:
                try:
                    due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                    if due_date < today:
                        overdue_tasks.append(task_with_index)
                    elif due_date == today:
                        today_tasks.append(task_with_index)
                    else:
                        upcoming_tasks.append(task_with_index)
                except:
                    no_due_tasks.append(task_with_index)
        
        # 排序：過期 > 今天 > 未來 > 無期限
        sorted_tasks = overdue_tasks + today_tasks + upcoming_tasks + no_due_tasks
        
        # 創建作業按鈕（最多顯示10個）
        task_buttons = []
        for item in sorted_tasks[:10]:
            task = item["task"]
            index = item["index"]
            
            # 決定標籤和顏色
            due = task.get("due", "未設定")
            label_prefix = ""
            button_color = None
            
            if due != "未設定":
                try:
                    due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                    if due_date < today:
                        label_prefix = "🔥 "
                        button_color = "#DC2626"
                    elif due_date == today:
                        label_prefix = "⏰ "
                        button_color = "#F59E0B"
                    else:
                        label_prefix = "📅 "
                        button_color = "#3B82F6"
                except:
                    label_prefix = "📝 "
            else:
                label_prefix = "📝 "
            
            # 處理過長的任務名稱
            task_name = task.get("task", "未命名")
            if len(task_name) > 15:
                task_name = task_name[:14] + "..."
            
            button = {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": f"{label_prefix}{task_name}",
                    "data": f"confirm_complete_{index}"
                },
                "style": "secondary",
                "height": "sm"
            }
            
            if button_color:
                button["color"] = button_color
            
            task_buttons.append(button)
        
        # 將按鈕分組（每行最多2個）
        button_rows = []
        for i in range(0, len(task_buttons), 2):
            row_buttons = task_buttons[i:i+2]
            # 如果只有一個按鈕，加入填充
            if len(row_buttons) == 1:
                row_buttons.append({"type": "filler"})
            
            button_rows.append({
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": row_buttons
            })
        
        # 添加按鈕到body
        if button_rows:
            bubble["body"]["contents"].extend(button_rows)
        
        # 如果作業太多，顯示提示
        if len(incomplete_tasks) > 10:
            bubble["body"]["contents"].extend([
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": f"📋 還有 {len(incomplete_tasks) - 10} 項作業未顯示",
                    "size": "xs",
                    "color": "#6B7280",
                    "align": "center",
                    "margin": "sm"
                }
            ])
        
        # Footer
        bubble["footer"] = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "🔄 批次完成多項作業",
                        "data": "batch_complete_tasks"
                    },
                    "style": "primary",
                    "color": "#7C3AED"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_complete_task"
                    },
                    "style": "secondary"
                }
            ]
        }
        
        return bubble

    @staticmethod
    def handle_confirm_complete(user_id, task_index, reply_token):
        """處理確認完成單一作業"""
        tasks = load_data(user_id)
        
        if task_index < 0 or task_index >= len(tasks):
            CompleteTaskFlowManager._send_error(reply_token)
            return
        
        task = tasks[task_index]
        
        # 創建確認卡片
        bubble = CompleteTaskFlowManager._create_confirmation_bubble(task, task_index)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="確認完成作業",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def _create_confirmation_bubble(task, task_index):
        """創建確認完成作業的卡片"""
        task_name = task.get("task", "未命名")
        category = task.get("category", "未分類")
        estimated_time = task.get("estimated_time", 0)
        due = task.get("due", "未設定")
        
        # 計算完成時間統計
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        completion_info = ""
        
        if due != "未設定":
            try:
                due_date = datetime.datetime.strptime(due, "%Y-%m-%d").date()
                today = now.date()
                days_diff = (due_date - today).days
                
                if days_diff < 0:
                    completion_info = f"已延遲 {abs(days_diff)} 天"
                    info_color = "#DC2626"
                elif days_diff == 0:
                    completion_info = "準時完成！"
                    info_color = "#10B981"
                else:
                    completion_info = f"提前 {days_diff} 天完成"
                    info_color = "#3B82F6"
            except:
                completion_info = ""
                info_color = "#666666"
        
        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "🎉 確認完成作業",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold"
                    }
                ],
                "backgroundColor": "#10B981",
                "paddingAll": "15px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": task_name,
                        "size": "lg",
                        "weight": "bold",
                        "wrap": True,
                        "color": "#1F2937"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "📚 類型",
                                        "size": "sm",
                                        "color": "#6B7280",
                                        "flex": 2
                                    },
                                    {
                                        "type": "text",
                                        "text": category,
                                        "size": "sm",
                                        "color": "#1F2937",
                                        "flex": 3,
                                        "weight": "bold"
                                    }
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "⏱️ 預估時間",
                                        "size": "sm",
                                        "color": "#6B7280",
                                        "flex": 2
                                    },
                                    {
                                        "type": "text",
                                        "text": f"{estimated_time} 小時",
                                        "size": "sm",
                                        "color": "#1F2937",
                                        "flex": 3,
                                        "weight": "bold"
                                    }
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "📅 截止日期",
                                        "size": "sm",
                                        "color": "#6B7280",
                                        "flex": 2
                                    },
                                    {
                                        "type": "text",
                                        "text": due if due != "未設定" else "無期限",
                                        "size": "sm",
                                        "color": "#1F2937",
                                        "flex": 3,
                                        "weight": "bold"
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
                            "label": "✅ 確認完成",
                            "data": f"execute_complete_{task_index}"
                        },
                        "style": "primary",
                        "color": "#10B981",
                        "flex": 2
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "❌ 取消",
                            "data": "cancel_complete_task"
                        },
                        "style": "secondary",
                        "flex": 1
                    }
                ]
            }
        }
        
        # 如果有完成時間資訊，添加到 body
        if completion_info:
            bubble["body"]["contents"].extend([
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🏆 完成狀態",
                            "size": "sm",
                            "color": "#6B7280",
                            "flex": 2
                        },
                        {
                            "type": "text",
                            "text": completion_info,
                            "size": "sm",
                            "color": info_color,
                            "flex": 3,
                            "weight": "bold"
                        }
                    ]
                }
            ])
        
        return bubble

    @staticmethod
    def execute_complete_task(user_id, task_index, reply_token):
        """執行完成作業"""
        try:
            tasks = load_data(user_id)
            
            if task_index < 0 or task_index >= len(tasks):
                CompleteTaskFlowManager._send_error(reply_token)
                return
            
            # 標記為完成
            task = tasks[task_index]
            task["done"] = True
            task["completed_at"] = datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=8))
            ).strftime("%Y-%m-%d %H:%M:%S")
            
            save_data(user_id, tasks)
            
            # 創建成功訊息
            CompleteTaskFlowManager._send_success_message(user_id, task, reply_token)
            
        except Exception as e:
            print(f"完成作業失敗：{e}")
            CompleteTaskFlowManager._send_error(reply_token)

    @staticmethod
    def _send_success_message(user_id, completed_task, reply_token):
        """發送成功完成的訊息"""
        tasks = load_data(user_id)
        remaining_tasks = [t for t in tasks if not t.get("done", False)]
        
        # 創建成功訊息卡片
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "🎉 太棒了！",
                        "size": "xl",
                        "weight": "bold",
                        "color": "#10B981",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": f"已完成：{completed_task.get('task', '未命名')}",
                        "size": "md",
                        "wrap": True,
                        "align": "center",
                        "margin": "md"
                    },
                    {
                        "type": "separator",
                        "margin": "lg"
                    },
                    {
                        "type": "text",
                        "text": f"剩餘 {len(remaining_tasks)} 項作業待完成",
                        "size": "sm",
                        "color": "#6B7280",
                        "align": "center",
                        "margin": "md"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": []
            }
        }
        
        # 如果還有作業未完成，提供繼續完成的按鈕
        if remaining_tasks:
            bubble["footer"]["contents"].append({
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": "✅ 繼續完成其他作業",
                    "data": "complete_task"
                },
                "style": "primary",
                "color": "#10B981"
            })
        
        bubble["footer"]["contents"].append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": "📋 查看所有作業",
                "data": "view_tasks"
            },
            "style": "secondary"
        })
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="作業完成",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def handle_batch_complete(user_id, reply_token):
        """處理批次完成作業"""
        tasks = load_data(user_id)
        incomplete_tasks = [(i, task) for i, task in enumerate(tasks) if not task.get("done", False)]
        
        if not incomplete_tasks:
            CompleteTaskFlowManager._send_no_tasks_message(reply_token)
            return
        
        # 清除之前的選擇
        from firebase_utils import clear_batch_selection
        clear_batch_selection(user_id)
        
        # 設定用戶狀態
        set_user_state(user_id, "batch_selecting_tasks")
        
        # 創建批次選擇介面
        bubble = CompleteTaskFlowManager._create_batch_selection_bubble(incomplete_tasks, user_id)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="批次完成作業",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def _create_batch_selection_bubble(incomplete_tasks, user_id):
        """創建批次選擇作業的卡片"""
        # 獲取當前選中的項目
        from firebase_utils import get_batch_selection
        selected_indices = get_batch_selection(user_id)
        
        bubble = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📋 批次完成作業",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold"
                    },
                    {
                        "type": "text",
                        "text": f"已選擇 {len(selected_indices)} 項",
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
                "spacing": "sm",
                "contents": [
                    {
                        "type": "text",
                        "text": "點選要完成的作業（可多選）",
                        "size": "md",
                        "color": "#4B5563",
                        "margin": "sm"
                    }
                ]
            }
        }
        
        # 創建選擇框列表
        for i, (index, task) in enumerate(incomplete_tasks[:15]):  # 最多顯示15個
            task_name = task.get("task", "未命名")
            if len(task_name) > 20:
                task_name = task_name[:19] + "..."
            
            # 檢查是否已選中
            is_selected = index in selected_indices
            checkbox_icon = "☑" if is_selected else "☐"
            button_color = "#10B981" if is_selected else None
            
            checkbox = {
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "margin": "md",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": f"{checkbox_icon} {task_name}",
                            "data": f"toggle_batch_{index}"
                        },
                        "style": "secondary",
                        "height": "sm"
                    }
                ]
            }
            
            if button_color:
                checkbox["contents"][0]["color"] = button_color
            
            bubble["body"]["contents"].append(checkbox)
        
        # Footer
        bubble["footer"] = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": f"✅ 完成選中項目 ({len(selected_indices)})",
                        "data": "execute_batch_complete"
                    },
                    "style": "primary",
                    "color": "#10B981",
                    "flex": 2
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "❌ 取消",
                        "data": "cancel_complete_task"
                    },
                    "style": "secondary",
                    "flex": 1
                }
            ]
        }
        
        # 如果沒有選中任何項目，禁用完成按鈕
        if len(selected_indices) == 0:
            bubble["footer"]["contents"][0]["style"] = "secondary"
            bubble["footer"]["contents"][0]["color"] = "#9CA3AF"
        
        return bubble

    @staticmethod
    def handle_toggle_batch_selection(user_id, task_index, reply_token):
        """處理批次選擇的切換"""
        from firebase_utils import toggle_batch_selection, load_data
        
        # 切換選擇狀態
        success, action, total_selected = toggle_batch_selection(user_id, task_index)
        
        if not success:
            CompleteTaskFlowManager._send_error(reply_token)
            return
        
        # 重新顯示更新後的選擇介面
        tasks = load_data(user_id)
        incomplete_tasks = [(i, task) for i, task in enumerate(tasks) if not task.get("done", False)]
        bubble = CompleteTaskFlowManager._create_batch_selection_bubble(incomplete_tasks, user_id)
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="批次完成作業",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def execute_batch_complete(user_id, reply_token):
        """執行批次完成作業"""
        from firebase_utils import get_batch_selection, batch_complete_tasks, get_batch_selected_tasks
        
        # 獲取選中的作業
        selected_tasks = get_batch_selected_tasks(user_id)
        
        if not selected_tasks:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text="⚠️ 請先選擇要完成的作業")]
                    )
                )
            return
        
        # 執行批次完成
        selected_indices = [item["index"] for item in selected_tasks]
        success, completed_count = batch_complete_tasks(user_id, selected_indices)
        
        if not success:
            CompleteTaskFlowManager._send_error(reply_token)
            return
        
        # 清除用戶狀態
        clear_user_state(user_id)
        
        # 創建成功訊息
        CompleteTaskFlowManager._send_batch_success_message(user_id, completed_count, reply_token)

    @staticmethod
    def _send_batch_success_message(user_id, completed_count, reply_token):
        """發送批次完成成功的訊息"""
        tasks = load_data(user_id)
        remaining_tasks = [t for t in tasks if not t.get("done", False)]
        
        bubble = {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "🎉 批次完成成功！",
                        "size": "xl",
                        "weight": "bold",
                        "color": "#10B981",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": f"已完成 {completed_count} 項作業",
                        "size": "lg",
                        "align": "center",
                        "margin": "md"
                    },
                    {
                        "type": "separator",
                        "margin": "lg"
                    },
                    {
                        "type": "text",
                        "text": f"剩餘 {len(remaining_tasks)} 項作業待完成",
                        "size": "sm",
                        "color": "#6B7280",
                        "align": "center",
                        "margin": "md"
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": []
            }
        }
        
        if remaining_tasks:
            bubble["footer"]["contents"].append({
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": "✅ 繼續完成其他作業",
                    "data": "complete_task"
                },
                "style": "primary",
                "color": "#10B981"
            })
        
        bubble["footer"]["contents"].append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": "📋 查看所有作業",
                "data": "view_tasks"
            },
            "style": "secondary"
        })
        
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="批次完成成功",
                            contents=FlexContainer.from_dict(bubble)
                        )
                    ]
                )
            )

    @staticmethod
    def _send_error(reply_token):
        """發送錯誤訊息"""
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="❌ 發生錯誤，請重新操作")]
                )
            )

    @staticmethod
    def _send_no_tasks_message(reply_token):
        """發送沒有作業的訊息"""
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="✅ 太棒了！目前沒有未完成的作業")]
                )
            )


# ==================== 處理器函數 ====================

def handle_complete_task(user_id, reply_token):
    """完成作業 - 統一入口"""
    CompleteTaskFlowManager.start_complete_task_flow(user_id, reply_token)

def handle_confirm_complete(data, user_id, reply_token):
    """處理確認完成單一作業"""
    try:
        task_index = int(data.replace("confirm_complete_", ""))
        CompleteTaskFlowManager.handle_confirm_complete(user_id, task_index, reply_token)
    except ValueError:
        CompleteTaskFlowManager._send_error(reply_token)

def handle_execute_complete(data, user_id, reply_token):
    """執行完成作業"""
    try:
        task_index = int(data.replace("execute_complete_", ""))
        CompleteTaskFlowManager.execute_complete_task(user_id, task_index, reply_token)
    except ValueError:
        CompleteTaskFlowManager._send_error(reply_token)

def handle_batch_complete_tasks(user_id, reply_token):
    """處理批次完成作業"""
    CompleteTaskFlowManager.handle_batch_complete(user_id, reply_token)

def handle_toggle_batch(data, user_id, reply_token):
    """處理批次選擇切換"""
    try:
        task_index = int(data.replace("toggle_batch_", ""))
        CompleteTaskFlowManager.handle_toggle_batch_selection(user_id, task_index, reply_token)
    except ValueError:
        CompleteTaskFlowManager._send_error(reply_token)

def handle_execute_batch_complete(user_id, reply_token):
    """執行批次完成"""
    CompleteTaskFlowManager.execute_batch_complete(user_id, reply_token)

def handle_cancel_complete_task(user_id, reply_token):
    """取消完成作業"""
    CompleteTaskFlowManager.cancel_complete_task(user_id, reply_token)