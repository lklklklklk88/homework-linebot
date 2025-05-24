import os, json, tempfile
import firebase_admin
from firebase_admin import credentials, db
import datetime

# Firebase 初始化
cred_json = os.getenv("GOOGLE_CREDENTIALS")
if not cred_json:
    raise Exception("GOOGLE_CREDENTIALS 環境變數未設定")

cred_dict = json.loads(cred_json)
cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".json") as temp:
    json.dump(cred_dict, temp)
    temp.flush()
    cred = credentials.Certificate(temp.name)
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv("FIREBASE_DB_URL")
    })

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
    
def save_remind_time(user_id, remind_time):
    """
    儲存使用者提醒時間到 Firebase
    """
    try:
        ref = db.reference(f"users/{user_id}/settings")
        ref.update({"remind_time": remind_time})
        return True
    except Exception as e:
        print(f"儲存提醒時間失敗：{e}")
        return False

def save_remind_time(user_id, time_string):
    meta = load_metadata(user_id) or {}
    meta["remind_time"] = time_string
    save_metadata(user_id, meta)

def load_metadata(user_id):
    ref = db.reference(f"users/{user_id}/meta")
    return ref.get()

def save_metadata(user_id, data):
    ref = db.reference(f"users/{user_id}/meta")
    ref.set(data)

