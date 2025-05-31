import os, json, tempfile
import firebase_admin
from firebase_admin import credentials, db
import datetime
import atexit

# Firebase 初始化
cred_json = os.getenv("GOOGLE_CREDENTIALS")
if not cred_json:
    raise Exception("GOOGLE_CREDENTIALS 環境變數未設定")

cred_dict = json.loads(cred_json)
cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

temp_file_path = None

with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json") as temp:
    temp_file_path = temp.name
    json.dump(cred_dict, temp)
    temp.flush()
    cred = credentials.Certificate(temp.name)
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv("FIREBASE_DB_URL")
    })

# 註冊清理函數
def cleanup_temp_file():
    global temp_file_path
    if temp_file_path and os.path.exists(temp_file_path):
        try:
            os.unlink(temp_file_path)
            print(f"已清理暫存檔案：{temp_file_path}")
        except Exception as e:
            print(f"清理暫存檔案失敗：{e}")

atexit.register(cleanup_temp_file)

# 作業資料 CRUD
def load_data(user_id):
    ref = db.reference(f"users/{user_id}/tasks")
    data = ref.get()
    return data if data else []

def save_data(user_id, data):
    ref = db.reference(f"users/{user_id}/tasks")
    ref.set(data)

# 使用者狀態與暫存任務
def set_user_state(user_id, state):
    db.reference(f"users/{user_id}/state").set(state)

def get_user_state(user_id):
    return db.reference(f"users/{user_id}/state").get()

def clear_user_state(user_id):
    db.reference(f"users/{user_id}/state").delete()

def set_temp_task(user_id, task):
    db.reference(f"users/{user_id}/temp_task").set(task)

def get_temp_task(user_id):
    return db.reference(f"users/{user_id}/temp_task").get() or {}

def clear_temp_task(user_id):
    db.reference(f"users/{user_id}/temp_task").delete()

def update_task_status(user_id, task_name, status):
    """
    更新任務狀態
    """
    try:
        tasks = load_data(user_id)
        for task in tasks:
            if task["task"] == task_name:
                task["done"] = (status == "completed")
                save_data(user_id, tasks)
                return True
        return False
    except Exception as e:
        print(f"更新任務狀態時發生錯誤：{str(e)}")
        return False

def get_task_history(user_id):
    """
    獲取作業名稱歷史記錄
    """
    ref = db.reference(f"users/{user_id}/task_history")
    history = ref.get() or {"names": [], "types": [], "times": []}
    return history.get("names", []), history.get("types", []), history.get("times", [])

def update_task_history(user_id, task_name, task_type, estimated_time):
    """
    更新作業歷史記錄
    """
    ref = db.reference(f"users/{user_id}/task_history")
    history = ref.get() or {"names": [], "types": [], "times": []}
    
    # 確保所有必要的鍵都存在
    if "names" not in history:
        history["names"] = []
    if "types" not in history:
        history["types"] = []
    if "times" not in history:
        history["times"] = []
    
    # 更新名稱歷史
    if task_name not in history["names"]:
        history["names"].append(task_name)
        if len(history["names"]) > 10:  # 保留最近10筆
            history["names"].pop(0)
    
    # 更新類型歷史
    if task_type not in history["types"]:
        history["types"].append(task_type)
        if len(history["types"]) > 10:  # 保留最近10筆
            history["types"].pop(0)
    
    # 更新時間歷史
    time_str = f"{estimated_time}小時"
    if time_str not in history["times"]:
        history["times"].append(time_str)
        if len(history["times"]) > 10:  # 保留最近10筆
            history["times"].pop(0)
    
    ref.set(history)

def add_task(user_id, task):
    """
    新增任務到用戶的任務列表中
    """
    try:
        tasks = load_data(user_id)
        task["done"] = False  # 確保新任務的狀態為未完成
        tasks.append(task)
        save_data(user_id, tasks)
        return True
    except Exception as e:
        print(f"新增任務時發生錯誤：{str(e)}")
        return False

def get_remind_time(user_id):
    """獲取未完成作業提醒時間"""
    try:
        # 檢查是否已設定過
        ref = db.reference(f"users/{user_id}/remind_time")
        remind_time = ref.get()
        
        # 如果從未設定過，使用預設值並儲存
        if remind_time is None:
            remind_time = "08:00"
            ref.set(remind_time)
            print(f"[提醒] 為用戶 {user_id} 設定預設未完成作業提醒時間：{remind_time}")
        
        return remind_time
    except Exception as e:
        print(f"獲取提醒時間失敗：{e}")
        return "08:00"

def get_add_task_remind_time(user_id):
    """獲取新增作業提醒時間"""
    try:
        # 檢查是否已設定過
        ref = db.reference(f"users/{user_id}/add_task_remind_time")
        remind_time = ref.get()
        
        # 如果從未設定過，使用預設值並儲存
        if remind_time is None:
            remind_time = "17:00"
            ref.set(remind_time)
            print(f"[提醒] 為用戶 {user_id} 設定預設新增作業提醒時間：{remind_time}")
        
        return remind_time
    except Exception as e:
        print(f"獲取新增作業提醒時間失敗：{e}")
        return "17:00"

def get_task_remind_enabled(user_id):
    """獲取是否啟用未完成作業提醒"""
    try:
        ref = db.reference(f"users/{user_id}/task_remind_enabled")
        enabled = ref.get()
        
        # 如果從未設定過，預設為啟用
        if enabled is None:
            enabled = True
            ref.set(enabled)
            print(f"[提醒] 為用戶 {user_id} 設定預設未完成作業提醒狀態：啟用")
        
        return enabled
    except Exception as e:
        print(f"獲取未完成作業提醒狀態失敗：{e}")
        return True

def get_add_task_remind_enabled(user_id):
    """獲取是否啟用新增作業提醒"""
    try:
        ref = db.reference(f"users/{user_id}/add_task_remind_enabled")
        enabled = ref.get()
        
        # 如果從未設定過，預設為啟用
        if enabled is None:
            enabled = True
            ref.set(enabled)
            print(f"[提醒] 為用戶 {user_id} 設定預設新增作業提醒狀態：啟用")
        
        return enabled
    except Exception as e:
        print(f"獲取新增作業提醒狀態失敗：{e}")
        return True

def save_remind_time(user_id, time_str):
    """儲存未完成作業提醒時間"""
    try:
        db.reference(f"users/{user_id}/remind_time").set(time_str)
        # 變更時間後，重設今天的提醒狀態，允許新時間生效
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
        last_remind_date = db.reference(f"users/{user_id}/last_task_remind_date").get()
        
        # 如果今天已經提醒過，且新時間還沒到，則清除今天的提醒記錄
        if last_remind_date == today:
            current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%H:%M")
            if time_str > current_time:
                db.reference(f"users/{user_id}/last_task_remind_date").delete()
                print(f"[提醒] 清除用戶 {user_id} 今天的未完成作業提醒記錄，新時間 {time_str} 將生效")
        
        return True
    except Exception as e:
        print(f"儲存未完成作業提醒時間失敗：{e}")
        return False

def save_add_task_remind_time(user_id, time_str):
    """儲存新增作業提醒時間"""
    try:
        db.reference(f"users/{user_id}/add_task_remind_time").set(time_str)
        # 變更時間後，重設今天的提醒狀態，允許新時間生效
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
        last_remind_date = db.reference(f"users/{user_id}/last_add_task_remind_date").get()
        
        # 如果今天已經提醒過，且新時間還沒到，則清除今天的提醒記錄
        if last_remind_date == today:
            current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%H:%M")
            if time_str > current_time:
                db.reference(f"users/{user_id}/last_add_task_remind_date").delete()
                print(f"[提醒] 清除用戶 {user_id} 今天的新增作業提醒記錄，新時間 {time_str} 將生效")
        
        return True
    except Exception as e:
        print(f"儲存新增作業提醒時間失敗：{e}")
        return False

def save_task_remind_enabled(user_id, enabled):
    """儲存是否啟用未完成作業提醒"""
    try:
        db.reference(f"users/{user_id}/task_remind_enabled").set(enabled)
        return True
    except Exception as e:
        print(f"儲存未完成作業提醒狀態失敗：{e}")
        return False

def save_add_task_remind_enabled(user_id, enabled):
    """儲存是否啟用新增作業提醒"""
    try:
        db.reference(f"users/{user_id}/add_task_remind_enabled").set(enabled)
        return True
    except Exception as e:
        print(f"儲存新增作業提醒狀態失敗：{e}")
        return False

def load_metadata(user_id):
    ref = db.reference(f"users/{user_id}/meta")
    return ref.get()

def save_metadata(user_id, data):
    ref = db.reference(f"users/{user_id}/meta")
    ref.set(data)
    
def get_batch_selection(user_id):
    """
    獲取用戶批次選擇的作業索引列表
    返回: list of int - 被選中的作業索引
    """
    try:
        ref = db.reference(f"users/{user_id}/batch_selection")
        selection = ref.get()
        return selection if selection else []
    except Exception as e:
        print(f"獲取批次選擇失敗：{e}")
        return []

def toggle_batch_selection(user_id, task_index):
    """
    切換某個作業的選擇狀態
    如果已選中則取消，如果未選中則選中
    """
    try:
        selection = get_batch_selection(user_id)
        
        if task_index in selection:
            # 已選中，移除
            selection.remove(task_index)
            action = "取消選擇"
        else:
            # 未選中，添加
            selection.append(task_index)
            action = "選擇"
        
        # 儲存更新後的選擇
        db.reference(f"users/{user_id}/batch_selection").set(selection)
        return True, action, len(selection)
        
    except Exception as e:
        print(f"切換批次選擇失敗：{e}")
        return False, "", 0

def clear_batch_selection(user_id):
    """
    清除所有批次選擇
    通常在完成批次操作或取消時調用
    """
    try:
        db.reference(f"users/{user_id}/batch_selection").delete()
        return True
    except Exception as e:
        print(f"清除批次選擇失敗：{e}")
        return False

def get_batch_selected_tasks(user_id):
    """
    獲取所有被選中的作業詳細資訊
    返回: list of dict - 被選中的作業資料
    """
    try:
        selection = get_batch_selection(user_id)
        if not selection:
            return []
        
        tasks = load_data(user_id)
        selected_tasks = []
        
        for index in selection:
            if 0 <= index < len(tasks):
                selected_tasks.append({
                    "index": index,
                    "task": tasks[index]
                })
        
        return selected_tasks
        
    except Exception as e:
        print(f"獲取批次選擇的作業失敗：{e}")
        return []

def batch_complete_tasks(user_id, task_indices):
    """
    批次完成多個作業
    """
    try:
        tasks = load_data(user_id)
        completed_count = 0
        
        # 標記所有選中的作業為完成
        for index in task_indices:
            if 0 <= index < len(tasks) and not tasks[index].get("done", False):
                tasks[index]["done"] = True
                tasks[index]["completed_at"] = datetime.datetime.now(
                    datetime.timezone(datetime.timedelta(hours=8))
                ).strftime("%Y-%m-%d %H:%M:%S")
                completed_count += 1
        
        # 儲存更新後的作業列表
        save_data(user_id, tasks)
        
        # 清除批次選擇
        clear_batch_selection(user_id)
        
        return True, completed_count
        
    except Exception as e:
        print(f"批次完成作業失敗：{e}")
        return False, 0
    
def get_all_user_ids():
    ref = db.reference("users")
    users = ref.get()
    return list(users.keys()) if users else []