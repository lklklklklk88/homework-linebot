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

def save_data(data, user_id):
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
                save_data(tasks, user_id)
                return True
        return False
    except Exception as e:
        print(f"更新任務狀態時發生錯誤：{str(e)}")
        return False

def delete_task(user_id, task_name):
    """
    刪除任務
    """
    try:
        tasks = load_data(user_id)
        for i, task in enumerate(tasks):
            if task["task"] == task_name:
                del tasks[i]
                save_data(tasks, user_id)
                return True
        return False
    except Exception as e:
        print(f"刪除任務時發生錯誤：{str(e)}")
        return False

def delay_task(user_id, task_name):
    """
    延後任務
    """
    try:
        tasks = load_data(user_id)
        for task in tasks:
            if task["task"] == task_name:
                # 將截止日期延後一天
                if task.get("due") and task["due"] != "未設定":
                    try:
                        due_date = datetime.datetime.strptime(task["due"], "%Y-%m-%d")
                        new_due = (due_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                        task["due"] = new_due
                        save_data(tasks, user_id)
                        return True
                    except:
                        return False
                return False
        return False
    except Exception as e:
        print(f"延後任務時發生錯誤：{str(e)}")
        return False
