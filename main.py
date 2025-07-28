from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.checkbox import CheckBox
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import (StringProperty, ListProperty, 
                           NumericProperty, BooleanProperty,
                           DictProperty, ObjectProperty)
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import platform
from kivy.lang import Builder
from kivy.config import Config
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.graphics import Color, Rectangle
import json
import random
import os
import sys
import time
import sqlite3
from pathlib import Path
import pandas as pd
import re
from io import BytesIO
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

Config.set('graphics', 'multisamples', '0')
Config.set('kivy', 'window_impl', 'sdl2')

ANDROID = False
if platform == 'android':
    try:
        from jnius import autoclass, cast
        from android import activity, mActivity
        from android.storage import app_storage_path

        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        Environment = autoclass('android.os.Environment')
        Context = autoclass('android.content.Context')
        File = autoclass('java.io.File')
        FileInputStream = autoclass('java.io.FileInputStream')
        FileOutputStream = autoclass('java.io.FileOutputStream')
        System = autoclass('java.lang.System')

        mActivity = PythonActivity.mActivity
        context = mActivity.getApplicationContext()
        ANDROID = True
    except Exception as e:
        print(f"Android初始化失败: {e}")
        ANDROID = False

def check_android_storage_permission():
    if platform != 'android':
        return True

    try:
        from android.permissions import request_permissions, Permission, check_permission

        request_permissions([
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE
        ])

        if not check_permission(Permission.READ_EXTERNAL_STORAGE):
            return False

        if int(mActivity.getApplicationInfo().targetSdkVersion) >= 30:
            if not System.getenv("EXTERNAL_STORAGE"):
                intent = Intent("android.settings.MANAGE_APP_ALL_FILES_ACCESS_PERMISSION")
                intent.setData(Uri.parse("package:" + mActivity.getPackageName()))
                mActivity.startActivity(intent)
                return False
            
        return True
    except:
        return False

def get_android_download_dir():
    if platform == 'android':
        from jnius import autoclass
        Environment = autoclass('android.os.Environment')
        download_dir = Environment.getExternalStoragePublicDirectory(
            Environment.DIRECTORY_DOWNLOADS
        ).getAbsolutePath()
        return download_dir
    return None

class QuizDatabase:
    def __init__(self, db_path='data/quiz.db'):
        self.db_path = db_path
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        if not os.path.exists(self.db_path):
            open(self.db_path, 'a').close()

        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quizzes'")
        table_exists = cursor.fetchone()

        if not table_exists:
            cursor.execute('''
            CREATE TABLE quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                source_type TEXT DEFAULT 'json'
            )
            ''')

            cursor.execute('''
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                options TEXT NOT NULL,
                answer TEXT NOT NULL,
                type TEXT NOT NULL,
                score INTEGER DEFAULT 1,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            )
            ''')
            self.conn.commit()
            return

        cursor.execute("PRAGMA table_info(quizzes)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'source_type' not in columns:
            try:
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute('''
                CREATE TABLE quizzes_temp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    source_type TEXT DEFAULT 'json'
                )
                ''')

                cursor.execute('''
                INSERT INTO quizzes_temp (id, name, description, source_type)
                SELECT id, name, description, 'json' FROM quizzes
                ''')

                cursor.execute("DROP TABLE quizzes")
                cursor.execute("ALTER TABLE quizzes_temp RENAME TO quizzes")
                cursor.execute("COMMIT")
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise e

        self.conn.commit()

    def get_available_quizzes(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT name FROM quizzes')
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []

    def get_questions_by_quiz_name(self, quiz_name):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT 
            q.question, 
            q.options, 
            q.answer, 
            q.type, 
            q.score
        FROM questions q
        JOIN quizzes qu ON q.quiz_id = qu.id
        WHERE qu.name = ?
        ''', (quiz_name,))

        questions = []
        for row in cursor.fetchall():
            question, options_json, answer, q_type, score = row
            questions.append({
                'question': question,
                'options': json.loads(options_json),
                'answer': json.loads(answer) if q_type == 'multi' else answer,
                'type': q_type,
                'score': score
            })
        return questions

    def get_quiz_info(self, quiz_name):
        cursor = self.conn.cursor()

        cursor.execute('PRAGMA table_info(quizzes)')
        columns = [column[1] for column in cursor.fetchall()]
        has_source_type = 'source_type' in columns

        if has_source_type:
            cursor.execute('''
            SELECT q.id, q.name, q.description, COUNT(qu.id) as question_count, q.source_type
            FROM quizzes q
            LEFT JOIN questions qu ON q.id = qu.quiz_id
            WHERE q.name = ?
            GROUP BY q.id
            ''', (quiz_name,))
        else:
            cursor.execute('''
            SELECT q.id, q.name, q.description, COUNT(qu.id) as question_count
            FROM quizzes q
            LEFT JOIN questions qu ON q.id = qu.quiz_id
            WHERE q.name = ?
            GROUP BY q.id
            ''', (quiz_name,))

        result = cursor.fetchone()
        if not result:
            return None

        if has_source_type:
            return {
                'id': result[0],
                'name': result[1],
                'description': result[2],
                'question_count': result[3],
                'source_type': result[4] if len(result) > 4 else 'json'
            }
        else:
            return {
                'id': result[0],
                'name': result[1],
                'description': result[2],
                'question_count': result[3],
                'source_type': 'json'
            }

    def add_quiz(self, quiz_name, questions_data, description="", source_type="json"):
        cursor = self.conn.cursor()

        cursor.execute('''
        INSERT OR REPLACE INTO quizzes (name, description, source_type)
        VALUES (?, ?, ?)
        ''', (quiz_name, description, source_type))

        cursor.execute('SELECT id FROM quizzes WHERE name = ?', (quiz_name,))
        quiz_id = cursor.fetchone()[0]

        cursor.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))

        for q in questions_data:
            cursor.execute('''
            INSERT INTO questions (
                quiz_id, question, options, answer, type, score
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                quiz_id,
                q['question'],
                json.dumps(q['options'], ensure_ascii=False),
                json.dumps(q['answer'], ensure_ascii=False) if isinstance(q['answer'], list) else q['answer'],
                q.get('type', 'single'),
                q.get('score', 1)
            ))

        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

class ExcelImportScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._popup = None
        self.file_chooser = None
        self.selected_file_uri = None
        self.setup_ui()

    def setup_ui(self):
        self.clear_widgets()
        
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        if platform == 'android':
            btn = Button(
                text='选择Excel文件',
                size_hint_y=None,
                height=dp(60),
                on_press=self.show_android_file_chooser
            )
            layout.add_widget(btn)
        else:
            self.show_kivy_file_chooser()
            return
            
        cancel_btn = Button(
            text='取消',
            size_hint_y=None,
            height=dp(50),
            on_press=self.cancel_import
        )
        layout.add_widget(cancel_btn)
        
        self.add_widget(layout)

    def show_android_file_chooser(self, instance=None):
        if not ANDROID:
            return
            
        try:
            if not check_android_storage_permission():
                self.show_message("需要存储权限")
                return

            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("*/*")

            mime_types = [
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ]
            intent.putExtra(Intent.EXTRA_MIME_TYPES, mime_types)

            def on_activity_result(request_code, result_code, intent):
                if request_code == 1001 and result_code == -1:  # RESULT_OK
                    uri = intent.getData()
                    self.process_android_file(uri)
                    
            activity.bind(on_activity_result=on_activity_result)

            mActivity.startActivityForResult(intent, 1001)
            
        except Exception as e:
            print(f"文件选择器错误: {e}")
            self.show_message("无法打开文件选择器")

    def process_android_file(self, uri):
        try:
            self.show_loading_popup("正在处理文件...")

            import threading
            thread = threading.Thread(
                target=self._process_android_file,
                args=(uri,),
                daemon=True
            )
            thread.start()
            
        except Exception as e:
            self.show_message(f"文件处理错误: {str(e)}")


    def _process_android_file(self, uri):
        try:
            display_name = self._get_display_name(uri)

            temp_dir = os.path.join(app_storage_path(), 'temp_import')
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, 'import_temp.xlsx')

            import threading
            thread = threading.Thread(
                target=self._copy_file_thread,
                args=(uri, temp_path, display_name),
                daemon=True
            )
            thread.start()
            
        except Exception as e:
            Clock.schedule_once(lambda dt, msg=f"准备导入失败: {str(e)}": self.show_message(msg))

    def _get_display_name(self, uri):
        from jnius import cast
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        ContentResolver = autoclass('android.content.ContentResolver')
        
        cursor = None
        try:
            cursor = PythonActivity.mActivity.getContentResolver().query(
                cast('android.net.Uri', uri), 
                None, None, None, None
            )
            if cursor and cursor.moveToFirst():
                name_index = cursor.getColumnIndex("_display_name")
                if name_index != -1:
                    name = cursor.getString(name_index)
                    return os.path.splitext(name)[0]
        except Exception as e:
            print(f"获取文件名出错: {e}")
        finally:
            if cursor:
                cursor.close()
        return "未命名题库"

    def _copy_file_thread(self, uri, temp_path, display_name):
        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            cr = PythonActivity.mActivity.getContentResolver()
            input_stream = cr.openInputStream(cast('android.net.Uri', uri))
            
            with open(temp_path, 'wb') as f:
                buf = bytearray(8192)
                while True:
                    bytes_read = input_stream.read(buf)
                    if bytes_read == -1: break
                    f.write(buf[:bytes_read])

            Clock.schedule_once(lambda dt: self.show_name_dialog(temp_path, display_name))
            
        except Exception as e:
            Clock.schedule_once(lambda dt, msg=f"文件复制失败: {str(e)}": self.show_message(msg))
        finally:
            try:
                input_stream.close()
            except:
                pass

    @mainthread
    def show_name_dialog(self, file_path, suggested_name):
        padding = 20
        spacing = 15

        content = BoxLayout(
            orientation='vertical',
            spacing=spacing,
            padding=[padding, padding, padding, padding],
            size_hint=(1, None),
            height=200
        )

        title_label = Label(
            text="请为题库命名",
            size_hint_y=None,
            height=50,
            font_name='simhei',
            font_size='20sp',
            halign='center'
        )

        name_input = TextInput(
            text=suggested_name,
            multiline=False,
            size_hint_y=None,
            height=100,
            font_name='simhei',
            font_size='18sp',
            padding=[20, 20]
        )

        btn_layout = BoxLayout(
            spacing=10,
            size_hint_y=None,
            height=300
        )

        cancel_btn = Button(
            text="取消",
            size_hint_x=0.5,
            font_size='18sp'
        )

        confirm_btn = Button(
            text="确定",
            size_hint_x=0.5,
            font_size='18sp'
        )

        content.add_widget(title_label)
        content.add_widget(name_input)
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(confirm_btn)
        content.add_widget(btn_layout)

        total_height = (
            title_label.height +
            name_input.height +
            btn_layout.height +
            (padding * 2) +
            (spacing * 2)
        )
        content.height = total_height

        def confirm(instance):
            quiz_name = name_input.text.strip()
            if not quiz_name:
                self.show_message("题库名称不能为空")
                return
            
            popup.dismiss()
            self._safe_import_quiz(file_path, quiz_name)
        
        confirm_btn.bind(on_press=confirm)
        cancel_btn.bind(on_press=lambda x: popup.dismiss())

        popup = Popup(
            title='',
            title_font='simhei',
            content=content,
            size_hint=(0.85, None),
            height=total_height + 40,
            auto_dismiss=False
        )
        popup.open()

    def _safe_import_quiz(self, file_path, quiz_name):
        processing_popup = Popup(
            title='处理中',
            title_font='simhei',
            content=Label(text="正在导入题库...", font_size='18sp'),
            size_hint=(0.7, 0.4)
        )
        processing_popup.open()

        Clock.schedule_once(
            lambda dt: self._execute_import(file_path, quiz_name, processing_popup),
            0.2
        )

    def _execute_import(self, file_path, quiz_name, processing_popup):
        try:
            app = App.get_running_app()

            if not hasattr(app, 'db'):
                app.db = QuizDatabase()

            try:
                if file_path.endswith('.xlsx'):
                    df = pd.read_excel(file_path, engine='openpyxl')
                else:
                    df = pd.read_excel(file_path, engine='xlrd')
            except Exception as e:
                raise Exception(f"Excel读取错误: {str(e)}")

            questions = self.process_excel_data(df)
            if not questions:
                raise Exception("未找到有效题目数据")

            existing = app.db.get_available_quizzes()
            while quiz_name in existing:
                if re.search(r'\(\d+\)$', quiz_name):
                    quiz_name = re.sub(r'\(\d+\)$', lambda m: f"({int(m.group(1))+1})", quiz_name)
                else:
                    quiz_name = f"{quiz_name}(1)"

            app.db.add_quiz(quiz_name, questions, source_type="excel")

            Clock.schedule_once(lambda dt: (
                processing_popup.dismiss(),
                self.show_message(f"成功导入【{quiz_name}】(共{len(questions)}题)"),
                setattr(self.manager, 'current', 'file_select'),
                self.manager.get_screen('file_select').load_quiz_list()
            ))
            
        except Exception as e:
            Clock.schedule_once(lambda dt: (
                processing_popup.dismiss(),
                self.show_message(f"导入失败: {str(e)}")
            ))
        finally:
            try:
                os.remove(file_path)
            except:
                pass

    def _safe_import(self, file_path, quiz_name, processing_popup):
        try:
            app = App.get_running_app()
            if not hasattr(app, 'db') or app.db.conn is None:
                app.db = QuizDatabase()

            try:
                if file_path.endswith('.xlsx'):
                    df = pd.read_excel(file_path, engine='openpyxl')
                else:
                    df = pd.read_excel(file_path, engine='xlrd')
            except Exception as e:
                raise Exception(f"读取Excel失败: {str(e)}")

            questions = self.process_excel_data(df)
            if not questions:
                raise Exception("Excel中没有找到有效的题目数据")

            existing = app.db.get_available_quizzes()
            while quiz_name in existing:
                base_name = re.sub(r'\(\d+\)$', '', quiz_name)
                counter = 1
                while f"{base_name}({counter})" in existing:
                    counter += 1
                quiz_name = f"{base_name}({counter})"

            app.db.add_quiz(quiz_name, questions, source_type="excel")

            self.show_message(f"成功导入题库【{quiz_name}】共{len(questions)}道题目")

            self.manager.current = 'file_select'
            self.manager.get_screen('file_select').load_quiz_list()
            
        except Exception as e:
            self.show_message(f"导入失败: {str(e)}")
        finally:
            processing_popup.dismiss()
            try:
                os.remove(file_path)
            except:
                pass

    def show_kivy_file_chooser(self):
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        self.file_chooser = FileChooserListView(
            filters=['*.xls', '*.xlsx'],
            font_name='simhei',
            size_hint=(1, 1)
        )
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50))
        import_btn = Button(text='导入', on_press=self.import_excel)
        cancel_btn = Button(text='取消', on_press=self.cancel_import)
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(import_btn)
        
        layout.add_widget(self.file_chooser)
        layout.add_widget(btn_layout)
        
        self.clear_widgets()
        self.add_widget(layout)

    def import_excel(self, instance=None):
        if platform == 'android':
            self.show_android_file_chooser()
            return

        if not self.file_chooser or not self.file_chooser.selection:
            self.show_message('请选择Excel文件')
            return

        file_path = self.file_chooser.selection[0]
        self._process_import(file_path)

    def _process_import(self, file_path):
        self.show_loading_popup("正在导入题库...")
        Clock.schedule_once(lambda dt: self._do_import(file_path), 0.1)

    def _do_import(self, file_path, quiz_name):
        try:
            if file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path, engine='openpyxl')
            else:
                df = pd.read_excel(file_path, engine='xlrd')
            
            questions = self.process_excel_data(df)

            app = App.get_running_app()
            existing = app.db.get_available_quizzes()
            while quiz_name in existing:
                quiz_name = f"{quiz_name}(1)"
            
            app.db.add_quiz(quiz_name, questions, source_type="excel")

            Clock.schedule_once(
                lambda dt: self._finalize_import(quiz_name, len(questions), 
                0)
            )
            
        except Exception as e:
            Clock.schedule_once(lambda dt, msg=f"导入失败: {str(e)}": self.show_message(msg))
        finally:
            try:
                os.remove(file_path)
            except:
                pass

    @mainthread
    def _finalize_import(self, quiz_name, question_count):
        self.show_message(f"成功导入题库【{quiz_name}】共{question_count}道题目")
        self.manager.current = 'file_select'
        self.manager.get_screen('file_select').load_quiz_list()

    def show_kivy_file_chooser(self):
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        self.file_chooser = FileChooserListView(
            filters=['*.xls', '*.xlsx'],
            font_name='simhei',
            size_hint=(1, 1)
        )
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(50))
        import_btn = Button(text='导入', on_press=self.import_excel)
        cancel_btn = Button(text='取消', on_press=self.cancel_import)
        btn_layout.add_widget(cancel_btn)
        btn_layout.add_widget(import_btn)
        
        layout.add_widget(self.file_chooser)
        layout.add_widget(btn_layout)
        
        self.clear_widgets()
        self.add_widget(layout)

    @mainthread
    def show_loading_popup(self, message):
        if hasattr(self, '_popup') and self._popup:
            self._popup.dismiss()

        content = BoxLayout(orientation='vertical', padding=10)
        content.add_widget(Label(text=message))
        self._popup = Popup(title='请稍候', title_font='simhei', content=content, size_hint=(0.8, 0.2))
        self._popup.open()

    @mainthread
    def dismiss_popup(self):
        if hasattr(self, '_popup') and self._popup:
            self._popup.dismiss()
            self._popup = None

    def process_excel_data(self, df):
        questions = []

        columns = [col.strip() for col in df.columns]

        serial_col = None
        for col in columns:
            if col in ['序号', '编号', '题号']:
                serial_col = col
                break

        question_col = None
        for col in columns:
            if col in ['题目', '题干', '问题', '试题']:
                question_col = col
                break

        if question_col is None:
            return questions

        type_col = None
        for col in columns:
            if col in ['题型', '题目类型', '类型']:
                type_col = col
                break

        option_cols = []
        for col in columns:
            if col.startswith('选项') or col in ['A', 'B', 'C', 'D', 'E', 'F']:
                option_cols.append(col)

        answer_col = None
        for col in columns:
            if col in ['答案', '正确答案', '标准答案']:
                answer_col = col
                break

        for idx, row in df.iterrows():
            serial = idx + 1
            if serial_col and serial_col in row:
                try:
                    serial = int(row[serial_col])
                except:
                    serial = idx + 1

            question = str(row[question_col]) if question_col in row else f"题目{serial}"

            q_type = 'single'
            if type_col and type_col in row:
                type_str = str(row[type_col]).strip()
                if type_str in ['多选', '多选题']:
                    q_type = 'multi'
                elif type_str in ['判断', '判断题']:
                    q_type = 'judge'

            options = []
            if q_type == 'judge':
                options = ['正确', '错误']
            elif option_cols:
                if len(option_cols) > 1:
                    for col in option_cols:
                        if col in row and pd.notna(row[col]):
                            options.append(str(row[col]))
                else:
                    option_str = str(row[option_cols[0]]) if option_cols[0] in row else ''
                    if option_str:
                        separators = [r'[A-Z][\.、:：]', r'\n', r'[;；]']
                        for sep in separators:
                            if re.search(sep, option_str):
                                split_options = re.split(sep, option_str)
                                options = [opt.strip() for opt in split_options if opt.strip()]
                                if options:
                                    break
                        
                        if not options:
                            pattern = r'([A-Z][\.、:：]\s*[^A-Z]+)'
                            matches = re.findall(pattern, option_str)
                            if matches:
                                options = [m.strip() for m in matches]
                            else:
                                options = [option_str]

            cleaned_options = []
            for opt in options:
                opt = re.sub(r'^[A-Z][\.、:：]\s*', '', opt.strip())
                cleaned_options.append(opt)
            options = cleaned_options

            answer = ''
            if answer_col and answer_col in row:
                answer = str(row[answer_col]).strip().upper()
                
                if q_type == 'multi':
                    answer = re.sub(r'[、\s]', ',', answer)
                    answer = [c for c in answer if c in 'ABCDEF']
                elif q_type == 'judge':
                    answer = 'A' if answer in ['A', '正确', '对', '是', 'Y', 'YES'] else 'B'

            score = 1
            if q_type == 'multi':
                score = 2

            question_data = {
                'question': f"{serial}. {question}",
                'options': options,
                'answer': answer if q_type != 'multi' else list(answer),
                'type': q_type,
                'score': score
            }

            questions.append(question_data)

        return questions

    @mainthread
    def show_message(self, message):
        content = Label(text=message, size_hint_y=None, height=dp(50))
        popup = Popup(title='提示', title_font='simhei', content=content, size_hint=(0.8, 0.3))
        content.bind(texture_size=lambda lbl, size: setattr(popup, 'height', size[1] + dp(100)))
        popup.open()

    def cancel_import(self, instance):
        self.manager.current = 'file_select'

class QuizScreen(Screen):
    def on_enter(self):
        self.update_option_buttons()
        app = App.get_running_app()
        if not app.question_start_time:
            app.reset_question_timer()

    def update_option_buttons(self):
        options_container = self.ids.options_container
        options_container.clear_widgets()

        app = App.get_running_app()
        if not hasattr(app, 'questions') or not app.questions:
            return

        current_question = app.questions[app.question_index]
        options = current_question.get('options', [])
        is_multi = current_question.get('type', 'single') in ['multi']
        single_types = ['single', 'grammar', 'vocabulary', 'culture', 'judge', 'cloze']

        for i, option in enumerate(options):        
            prefix = chr(65 + i)
            if is_multi:
                option_widget = MultiSelectOption(
                    prefix=prefix,
                    text=f"{prefix}. {option}"
                )

                if (len(app.user_answers) > app.question_index and 
                    isinstance(app.user_answers[app.question_index], list)):
                    option_widget.selected = prefix in app.user_answers[app.question_index]

                option_widget.bind(
                    selected=lambda instance, value, p=prefix: 
                    app.update_multi_answer(p, value))

                options_container.add_widget(option_widget)
            elif current_question.get('type') in single_types:
                btn = DynamicOptionButton(
                    text=f"{prefix}. {option}",
                    on_press=lambda instance, p=prefix: setattr(app, 'selected_answer', p),
                    group='answers_' + str(app.question_index),
                )

                if (len(app.user_answers) > app.question_index and 
                    isinstance(app.user_answers[app.question_index], str)):
                    btn.state = 'down' if app.user_answers[app.question_index] == prefix else 'normal'
                else:
                    btn.state = 'normal'

                options_container.add_widget(btn)

class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._layout_initialized = False

    def on_pre_enter(self):
        self._layout_initialized = False

    def on_enter(self):
        if not self._layout_initialized:
            try:
                self.update_layout()
                self._layout_initialized = True
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.clear_widgets()
                self.add_widget(Label(
                    text=f"加载结果出错: {str(e)}",
                    font_name='simhei',
                    font_size=dp(16)
                ))

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def update_layout(self):
        try:
            app = App.get_running_app()

            quiz_info = None
            if hasattr(app, 'last_quiz_name') and app.last_quiz_name:
                quiz_info = app.db.get_quiz_info(app.last_quiz_name)

            self.clear_widgets()

            root_layout = BoxLayout(orientation='vertical', spacing=dp(10))

            main_layout = BoxLayout(
                orientation='vertical',
                spacing=dp(10),
                size_hint=(1, 1)
            )

            top_info_bar = BoxLayout(
                size_hint_y=None,
                height=dp(100),
                orientation='vertical',
                spacing=dp(5),
                padding=[dp(10), dp(5)]
            )
            
            score_label = Label(
                text=f'测验结果 - 总分: {app.total_score}',
                font_name='simhei',
                font_size=dp(24),
                bold=True,
                halign='left',
                size_hint_y=None,
                height=dp(50)
            )
            
            time_label = Label(
                text=f'总用时: {self.format_time(app.total_time_used)}',
                font_name='simhei',
                font_size=dp(16),
                color=(0.4, 0.4, 0.4, 1),
                halign='left',
                size_hint_y=None,
                height=dp(30)
            )
            
            top_info_bar.add_widget(score_label)
            top_info_bar.add_widget(time_label)

            separator = BoxLayout(size_hint_y=None, height=dp(2))
            with separator.canvas.before:
                Color(rgb=(0.5, 0.5, 0.5))
                Rectangle(pos=separator.pos, size=separator.size)
            separator.bind(pos=self._update_rect, size=self._update_rect)

            scroll_view = ScrollView(
                size_hint=(1, 1),
                bar_width=dp(20),
                bar_color=(0.5, 0.5, 0.5, 0.7),
                scroll_type=['bars', 'content']
            )

            results_layout = GridLayout(
                cols=1,
                size_hint_y=None,
                spacing=dp(10),
                padding=[dp(10), dp(5)]
            )
            results_layout.bind(minimum_height=results_layout.setter('height'))

            for detail in app.result_details:
                item = BoxLayout(
                    orientation='vertical',
                    size_hint_y=None,
                    height=dp(200),
                    spacing=dp(5),
                    padding=[dp(10), dp(5)]
                )

                question_scroll = ScrollView(
                    size_hint_y=None, 
                    height=dp(100),
                    bar_width=dp(26),
                    bar_color=(0.5, 0.5, 0.5, 0.5)
                )
                question = Label(
                    text=detail['question'],
                    font_name='simhei',
                    font_size=dp(18),
                    size_hint_y=None,
                    text_size=(Window.width - dp(40), None),
                    halign='left',
                    valign='middle',
                    padding=(0, dp(5))
                )
                question.bind(texture_size=lambda lbl, val: setattr(lbl, 'height', max(dp(100), val[1])))
                question_scroll.add_widget(question)

                answer_label = Label(
                    text=f"您的答案: {detail['user_answer']} | 正确答案: {detail['correct_answer']}",
                    font_name='simhei',
                    font_size=dp(16),
                    color=(0, 0.7, 0, 1) if detail['is_correct'] else (1, 0, 0, 1),
                    text_size=(Window.width - dp(40), None),
                    halign='left',
                    valign='middle',
                    size_hint_y=None,
                    height=dp(40)
                )

                bottom_info = BoxLayout(
                    size_hint_y=None,
                    height=dp(30),
                    spacing=dp(10)
                )
                
                bottom_info.add_widget(Label(
                    text=f'得分: {detail["score"]}',
                    font_name='simhei',
                    font_size=dp(16),
                    color=(0, 0.7, 0, 1) if detail['is_correct'] else (1, 0, 0, 1)
                ))
                
                bottom_info.add_widget(Label(
                    text=f'用时: {detail["time_used"]}',
                    font_name='simhei',
                    font_size=dp(16),
                    color=(0.4, 0.4, 0.4, 1),
                    halign='right'
                ))

                item_separator = BoxLayout(size_hint_y=None, height=dp(2))
                with item_separator.canvas.before:
                    Color(rgb=(0.8, 0.8, 0.8))
                    Rectangle(pos=item_separator.pos, size=item_separator.size)
                item_separator.bind(pos=self._update_rect, size=self._update_rect)

                item.add_widget(question_scroll)
                item.add_widget(answer_label)
                item.add_widget(bottom_info)
                item.add_widget(item_separator)
                
                results_layout.add_widget(item)
            
            scroll_view.add_widget(results_layout)

            main_layout.add_widget(top_info_bar)
            main_layout.add_widget(separator)
            main_layout.add_widget(scroll_view)

            root_layout.add_widget(main_layout)

            btn_layout = BoxLayout(
                size_hint_y=None,
                height=dp(60),
                spacing=dp(10),
                padding=[dp(10), dp(5)]
            )

            restart_btn = Button(
                text='重新测试',
                on_press=lambda x: app.restart_quiz(),
                font_name='simhei',
                font_size=dp(20),
                background_color=(0.2, 0.6, 1, 1)
            )

            home_btn = Button(
                text='返回主页',
                on_press=lambda x: app.go_home(),
                font_name='simhei',
                font_size=dp(20),
                background_color=(0.8, 0.2, 0.2, 1)
            )

            if quiz_info and quiz_info.get('source_type', 'json') == 'excel':
                btn_layout.add_widget(restart_btn)
                btn_layout.add_widget(home_btn)
            else:
                btn_layout.add_widget(restart_btn)
                btn_layout.add_widget(home_btn)

            root_layout.add_widget(btn_layout)
            
            self.add_widget(root_layout)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.add_widget(Label(text=f"加载结果出错: {str(e)}", font_name='simhei'))

    def _update_rect(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            if instance.height == dp(2):
                Color(rgb=(0.5, 0.5, 0.5))
            else:
                Color(rgb=(0.8, 0.8, 0.8))
            Rectangle(pos=instance.pos, size=instance.size)

class FileSelectScreen(Screen):
    def on_enter(self):
        Clock.schedule_once(lambda dt: self.load_quiz_list(), 0.1)

    def load_quiz_list(self):
        self.clear_widgets()

        layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))

        import_btn = Button(
            text='导入Excel题库',
            size_hint_y=None,
            height=dp(60),
            font_name='simhei',
            background_color=(0.2, 0.6, 1, 1)
        )
        import_btn.bind(on_press=self.goto_import)
        layout.add_widget(import_btn)

        title = Label(
            text='选择题库',
            size_hint_y=None,
            height=dp(40),
            font_name='simhei',
            font_size=dp(20),
            bold=True
        )
        layout.add_widget(title)

        app = App.get_running_app()
        quiz_names = app.db.get_available_quizzes()

        if not quiz_names:
            no_quiz_label = Label(
                text='当前没有题库，请先导入题库',
                size_hint_y=None,
                height=dp(100),
                font_name='simhei',
                font_size=dp(18),
                color=(0.8, 0.2, 0.2, 1)
            )
            layout.add_widget(no_quiz_label)
        else:
            scroll = ScrollView()
            quiz_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(10))
            quiz_layout.bind(minimum_height=quiz_layout.setter('height'))
            scroll.add_widget(quiz_layout)
            layout.add_widget(scroll)
            
            for name in quiz_names:
                btn = Button(
                    text=name,
                    size_hint_y=None,
                    height=dp(60),
                    font_name='simhei'
                )
                btn.bind(on_press=lambda instance, n=name: app.load_questions(n))
                quiz_layout.add_widget(btn)

        self.add_widget(layout)

    def goto_import(self, instance):
        self.manager.current = 'excel_import'

class QuizApp(App):
    current_question = StringProperty('请选择考卷...')
    options = ListProperty([])
    question_index = NumericProperty(0)
    selected_answer = StringProperty('')
    total_score = NumericProperty(0)
    user_answers = ListProperty([])
    is_submitted = BooleanProperty(False)
    result_details = ListProperty([])
    last_quiz_name = StringProperty('')
    question_types = DictProperty({})
    total_time_used = NumericProperty(0)
    current_time_used = StringProperty('00:00')

    question_start_time = None
    time_event = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = QuizDatabase()

    def build(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.READ_EXTERNAL_STORAGE, 
                               Permission.WRITE_EXTERNAL_STORAGE])

        self.sm = ScreenManager()
        self.file_select_screen = FileSelectScreen(name='file_select')
        self.quiz_screen = QuizScreen(name='quiz')
        self.result_screen = ResultScreen(name='result')
        self.excel_import_screen = ExcelImportScreen(name='excel_import')

        self.sm.add_widget(self.file_select_screen)
        self.sm.add_widget(self.quiz_screen)
        self.sm.add_widget(self.result_screen)
        self.sm.add_widget(self.excel_import_screen)

        return self.sm

    def on_start(self):
        self.time_event = Clock.schedule_interval(self.update_timer, 1)

    def on_stop(self):
        self.db.close()
        if hasattr(self, 'time_event'):
            self.time_event.cancel()

    def reset_question_timer(self):
        self.question_start_time = time.time()
        self.current_time_used = '00:00'

    def record_current_question_time(self):
        if self.question_start_time and hasattr(self, 'question_time_records'):
            time_used = time.time() - self.question_start_time
            self.question_time_records[self.question_index] += time_used
            self.total_time_used += time_used
            self.question_start_time = None

    def update_timer(self, dt):
        if self.question_start_time and self.sm.current == 'quiz':
            elapsed = time.time() - self.question_start_time
            mins, secs = divmod(int(elapsed), 60)
            self.current_time_used = f"{mins:02d}:{secs:02d}"

    def get_available_quizzes(self):
        return self.db.get_available_quizzes()

    def load_questions(self, quiz_name):
        try:
            all_questions = self.db.get_questions_by_quiz_name(quiz_name)
            if not all_questions:
                raise ValueError(f"题库 '{quiz_name}' 中没有题目")
            
            self.start_quiz(all_questions)
            self.last_quiz_name = quiz_name
            return True

        except Exception as e:
            print(f"加载题库失败: {str(e)}")
            self.current_question = f"加载题目失败: {str(e)}"
            return False

    def start_quiz(self, all_questions):
        if hasattr(self, 'result_screen'):
            self.result_screen._layout_initialized = False
            self.result_screen.clear_widgets()

        question_count = min(30, len(all_questions))
        self.questions = random.sample(all_questions, question_count)

        self.user_answers = []
        self.question_types = {}
        self.total_time_used = 0
        self.question_time_records = []

        for i, q in enumerate(self.questions):
            q_type = q.get('type', 'single')
            self.question_types[i] = q_type
            if q_type == 'multi':
                self.user_answers.append([])
            else:
                self.user_answers.append('')
            self.question_time_records.append(0)

        self.question_index = 0
        self.is_submitted = False
        self.total_score = 0
        self.result_details = []
        self.selected_answer = ''
        self.reset_question_timer()

        self.update_question()
        self.sm.current = 'quiz'

    def update_question(self):
        if hasattr(self, 'questions') and self.questions:
            self.record_current_question_time()

            q = self.questions[self.question_index]
            self.current_question = '\n' + q.get('question', '')
            self.options = q.get('options', [])

            if len(self.user_answers) > self.question_index:
                if self.question_types.get(self.question_index) == 'multi':
                    pass
                else:
                    self.selected_answer = self.user_answers[self.question_index]
            else:
                self.selected_answer = ''

            if hasattr(self, 'quiz_screen'):
                self.quiz_screen.update_option_buttons()

            next_btn = self.quiz_screen.ids.next_btn
            next_btn.text = '交卷' if self.question_index == len(self.questions)-1 else '下一题'

            self.reset_question_timer()

    def update_multi_answer(self, prefix, is_selected):
        if (self.question_index >= len(self.user_answers) or 
            not isinstance(self.user_answers[self.question_index], list)):
            return

        current_answers = self.user_answers[self.question_index]

        if is_selected and prefix not in current_answers:
            current_answers.append(prefix)
        elif not is_selected and prefix in current_answers:
            current_answers.remove(prefix)

    def prev_question(self):
        if self.question_index > 0:
            self.record_current_question_time()

            if self.question_types.get(self.question_index) != 'multi':
                self.user_answers[self.question_index] = self.selected_answer
            self.question_index -= 1
            self.update_question()

    def next_question(self):
        if not hasattr(self, 'questions') or not self.questions:
            return

        self.record_current_question_time()

        if self.question_types.get(self.question_index) != 'multi':
            self.user_answers[self.question_index] = self.selected_answer

        if self.question_index < len(self.questions) - 1:
            self.question_index += 1
            self.update_question()
        else:
            self.submit_quiz()

    def submit_quiz(self):
        self.record_current_question_time()

        if self.question_types.get(self.question_index) != 'multi':
            self.user_answers[self.question_index] = self.selected_answer

        self.is_submitted = True
        self.total_score = 0
        self.result_details = []

        for i, user_answer in enumerate(self.user_answers):
            if i >= len(self.questions):
                continue

            correct_answer = self.questions[i].get('answer', '')
            q_type = self.questions[i].get('type', 'single')

            if q_type in ['single', 'grammar', 'vocabulary', 'culture', 'judge', 'cloze']:
                is_correct = str(user_answer).upper() == str(correct_answer).upper()
                score = self.questions[i].get('score', 0) if is_correct else 0
                self.total_score += score
            elif q_type == 'multi':
                correct_answers = sorted([x.upper() for x in (correct_answer if isinstance(correct_answer, list) else [correct_answer])])
                user_answers = sorted([x.upper() for x in (user_answer if isinstance(user_answer, list) else [])])
                is_correct = correct_answers == user_answers
                score = self.questions[i].get('score', 0) if is_correct else 0
                self.total_score += score

            time_used = self.question_time_records[i]
            minutes = int(time_used // 60)
            seconds = int(time_used % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"

            self.result_details.append({
                'question': f"{i+1}. {self.questions[i].get('question', '')}",
                'user_answer': ', '.join(user_answer) if isinstance(user_answer, list) else user_answer if user_answer else '未作答',
                'correct_answer': ', '.join(correct_answer) if isinstance(correct_answer, list) else correct_answer,
                'is_correct': is_correct,
                'score': score,
                'time_used': time_str,
                'type': q_type
            })

        self.sm.current = 'result'

    def restart_quiz(self):
        try:
            if hasattr(self, 'result_screen'):
                self.result_screen._layout_initialized = False
                self.result_screen.clear_widgets()

            self.question_index = 0
            self.selected_answer = ''
            self.total_score = 0
            self.user_answers = []
            self.is_submitted = False
            self.result_details = []
            self.total_time_used = 0
            self.current_time_used = '00:00'
            self.question_start_time = None

            if hasattr(self, 'last_quiz_name') and self.last_quiz_name:
                all_questions = self.db.get_questions_by_quiz_name(self.last_quiz_name)
                if all_questions:
                    self.start_quiz(all_questions)
                    return

            self.sm.current = 'file_select'

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.show_error_message(f"重新测试失败: {str(e)}")
            self.sm.current = 'file_select'

    def show_error_message(self, message):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(Label(text=message, font_name='simhei'))

        btn = Button(text='确定', size_hint_y=None, height=dp(50))
        popup = Popup(title='错误', title_font='simhei', content=content, size_hint=(0.8, 0.4))
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()

    def go_home(self):
        if hasattr(self, 'result_screen'):
            self.result_screen._layout_initialized = False
            self.result_screen.clear_widgets()

        self.question_index = 0
        self.selected_answer = ''
        self.total_score = 0
        self.user_answers = []
        self.is_submitted = False
        self.result_details = []
        self.total_time_used = 0
        self.current_time_used = '00:00'
        self.question_start_time = None

        self.sm.current = 'file_select'

class DynamicOptionButton(ToggleButton):
    pass

class MultiSelectOption(BoxLayout):
    prefix = StringProperty('')
    text = StringProperty('')
    selected = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bg_color = (0.3, 0.3, 0.3, 1)
        self.default_text_color = (1, 1, 1, 1)
        self.selected_bg_color = (0.1, 0.5, 0.8, 1)

        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(50)
        self.spacing = dp(10)
        self.padding = [dp(10), dp(5)]

        self._init_background()

        self.checkbox = CheckBox(
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            pos_hint={'center_y': 0.5}
        )

        self.text_container = BoxLayout(
            orientation='vertical',
            size_hint_x=1,
            size_hint_y=None
        )

        self.label = Label(
            text=self.text,
            size_hint_y=None,
            halign='left',
            valign='middle',
            font_size=dp(16),
            text_size=(None, None),
            padding=(0, dp(5)),
            color=self.default_text_color
        )
        self.label.bind(texture_size=self._update_height)

        self.click_area = Button(
            size_hint=(1, 1),
            background_color=(0, 0, 0, 0)
        )
        self.click_area.bind(on_press=self.toggle_selection)

        self.text_container.add_widget(self.label)
        self.text_container.add_widget(self.click_area)

        self.add_widget(self.checkbox)
        self.add_widget(self.text_container)

        self.bind(
            selected=self._update_style,
            text=self._update_text,
            pos=self._update_background,
            size=self._update_background
        )
        self.checkbox.bind(active=self.setter('selected'))

        self._update_height(self.label, self.label.texture_size)

    def _init_background(self):
        with self.canvas.before:
            Color(*self.bg_color)
            self.background_rect = Rectangle(pos=self.pos, size=self.size)

    def _update_background(self, *args):
        self.background_rect.pos = self.pos
        self.background_rect.size = self.size

    def _update_text(self, instance, value):
        self.label.text = value

    def _update_height(self, instance, value):
        text_height = value[1] + dp(20)
        min_height = dp(50)
        instance.height = max(text_height, min_height)
        self.height = instance.height + dp(10)
        self.text_container.height = instance.height

    def toggle_selection(self, instance):
        self.selected = not self.selected

    def _update_style(self, instance, value):
        with self.canvas.before:
            self.canvas.before.clear()
            if value:
                Color(*self.selected_bg_color)
                self.label.color = (0, 0, 0.5, 1)
            else:
                Color(*self.bg_color)
                self.label.color = self.default_text_color
            self.background_rect = Rectangle(pos=self.pos, size=self.size)

if platform == 'android':
    font_path = 'assets/font/simhei.ttf'
else:
    font_path = os.path.join('assets', 'font', 'simhei.ttf')

loaded = False
try:
    LabelBase.register(name='simhei', fn_regular=font_path)
    loaded = True
except Exception as e:
    print(f"第一种方式加载字体失败: {e}")

if not loaded and platform == 'android':
    try:
        from android.storage import app_storage_path
        font_path = os.path.join(app_storage_path(), 'font', 'simhei.ttf')
        LabelBase.register(name='simhei', fn_regular=font_path)
        loaded = True
    except Exception as e:
        print(f"第二种方式加载字体失败: {e}")

if not loaded:
    print(f"字体文件加载失败: {font_path}")
    LabelBase.register(name='simhei', fn_regular='DroidSans')

Builder.load_string('''
#:import dp kivy.metrics.dp
#:import Window kivy.core.window.Window

<BaseWidget>:
    font_name: 'simhei'

<Button>:
    font_name: 'simhei'
    font_size: '16sp'

<Label>:
    font_name: 'simhei'
    font_size: '16sp'
    text_size: self.width, None
    size_hint_y: None
    height: self.texture_size[1] + dp(20)

<DynamicOptionButton>:
    size_hint_y: None
    height: max(dp(50), self.texture_size[1] + dp(20))
    font_name: 'simhei'
    font_size: dp(16)
    text_size: self.width - dp(40), None
    padding: (dp(20), dp(10))
    halign: 'left'
    valign: 'middle'

<CheckBox>:
    size_hint: None, None
    size: dp(50), dp(50)
    canvas:
        Color:
            rgba: (0, 0, 0, 1) if self.active else (0.3, 0.3, 0.7, 1)


<MultiSelectOption>:
    size_hint_y: None
    height: self.text_container.height + dp(10) if hasattr(self, 'text_container') else dp(50)
    spacing: dp(10)
    padding: [dp(10), dp(5)]
    halign: 'left'
    valign: 'middle'

<QuizScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(10)

        BoxLayout:
            size_hint_y: None
            height: dp(180)
            orientation: 'vertical'

            BoxLayout:
                size_hint_y: None
                height: dp(30)
                Label:
                    text: '题目 ' + str(app.question_index + 1)
                    font_name: 'simhei'
                    font_size: dp(18)
                    halign: 'left'
                    size_hint_x: 0.8
                Label:
                    text: '用时: ' + app.current_time_used
                    font_name: 'simhei'
                    font_size: dp(16)
                    halign: 'right'
                    size_hint_x: 0.2

            ScrollView:
                Label:
                    id: question_label
                    text: app.current_question
                    font_name: 'simhei'
                    font_size: dp(18)
                    size_hint_y: None
                    height: max(self.texture_size[1], dp(160))
                    text_size: self.width - dp(20), None
                    padding: (dp(10), dp(10))
                    halign: 'left'
                    valign: 'middle'

        ScrollView:
            GridLayout:
                id: options_container
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
                padding: [dp(5), dp(5)]

        BoxLayout:
            size_hint_y: None
            height: dp(60)
            spacing: dp(5)

            Button:
                text: '上一题'
                on_press: app.prev_question()
                disabled: app.question_index == 0
                size_hint_x: 0.5
                font_name: 'simhei'
                font_size: dp(20)
                halign: 'center'

            Button:
                id: next_btn
                text: '下一题'
                on_press: app.next_question()
                size_hint_x: 0.5
                font_name: 'simhei'
                font_size: dp(20)
                halign: 'center'

<ResultScreen>:
    ScrollView:
        GridLayout:
            cols: 1
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(10)
            padding: dp(10)

            BoxLayout:
                size_hint_y: None
                height: dp(50)
                spacing: dp(10)

                BoxLayout:
                    orientation: 'vertical'
                    size_hint_x: 0.7
                    spacing: dp(2)
                    Label:
                        text: '测验结果 - 总分: ' + str(app.total_score)
                        font_name: 'simhei'
                        font_size: dp(24)
                        bold: True
                    Label:
                        text: '总用时: ' + root.format_time(app.total_time_used)
                        font_name: 'simhei'
                        font_size: dp(16)
                        color: (0.4, 0.4, 0.4, 1)

                Button:
                    text: '重新测试'
                    on_press: app.restart_quiz()
                    size_hint_x: 0.3
                    font_name: 'simhei'
                    font_size: dp(18)
                    background_color: (0.2, 0.6, 1, 1)

            BoxLayout:
                size_hint_y: None
                height: dp(2)
                canvas:
                    Color:
                        rgb: 0.5, 0.5, 0.5
                    Rectangle:
                        pos: self.pos
                        size: self.size

            RecycleView:
                data: app.result_details
                viewclass: 'ResultItem'
                size_hint_y: None
                height: dp(400)

                RecycleBoxLayout:
                    default_size: None, dp(80)
                    default_size_hint: 1, None
                    size_hint_y: None
                    height: self.minimum_height
                    orientation: 'vertical'
                    spacing: dp(5)

<ResultItem@BoxLayout>:
    orientation: 'vertical'
    padding: dp(10)
    size_hint_y: None
    height: self.minimum_height
    question: ''
    user_answer: ''
    correct_answer: ''
    is_correct: False
    score: 0
    time_used: '00:00'

    Label:
        text: root.question
        font_name: 'simhei'
        font_size: dp(18)
        size_hint_y: 1
        text_size: self.width - dp(20), None
        halign: 'left'
        valign: 'middle'
        padding: (dp(10), dp(10))

    BoxLayout:
        size_hint_y: None
        height: dp(30)
        spacing: dp(10)

        Label:
            text: '您的答案: ' + root.user_answer
            font_name: 'simhei'
            font_size: dp(16)
            color: (0, 0.7, 0, 1) if root.is_correct else (1, 0, 0, 1)

        Label:
            text: '正确答案: ' + root.correct_answer
            font_name: 'simhei'
            font_size: dp(16)
            color: (0, 0.7, 0, 1)

        Label:
            text: '得分: ' + str(root.score)
            font_name: 'simhei'
            font_size: dp(16)
            color: (0, 0.7, 0, 1) if root.is_correct else (1, 0, 0, 1)

    BoxLayout:
        size_hint_y: None
        height: dp(20)
        Label:
            text: '用时: ' + root.time_used
            font_name: 'simhei'
            font_size: dp(14)
            color: (0.4, 0.4, 0.4, 1)
            halign: 'right'

    BoxLayout:
        size_hint_y: None
        height: dp(2)
        canvas:
            Color:
                rgb: 0.8, 0.8, 0.8
            Rectangle:
                pos: self.pos
                size: self.size
''')

if __name__ == '__main__':
    QuizApp().run()
