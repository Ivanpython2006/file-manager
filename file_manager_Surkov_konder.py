import os
import shutil
import json
import shlex
import zipfile
import tarfile
import getpass
import datetime
from pathlib import Path
from typing import Dict, Optional, List

class UserManager: #управление пользователями
    def __init__(self, users_file: str = 'users.json'): 
        self.users_file = users_file # какой файл юзаем
        self.users = self._load_users() # загрузил существующих юзеров
        self.current_user: Optional[str] = None # пока никто не вошел
        
    def _load_users(self) -> Dict: #читает словарь с пользователями
        if os.path.exists(self.users_file): # проверил есть файл
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f) # прочитал юзеров из файла
        return {} # файла нет вернул пустой словарь
    
    def _save_users(self): #сохраняет пользователей в файл
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, indent=2, ensure_ascii=False) # сохранил юзеров в файл
    
    def register(self, username: str, password: str) -> bool: #регистрация нового пользователя
        if username in self.users: #занято ли имя
            print(f'Пользователь {username} уже существует.')
            return False # имя занято выход
        
        self.users[username] = {
            'password': password, #пароль пользователя
            'created': str(datetime.datetime.now()), #дата регистрации
            'total_space': 100 * 1024 * 1024 #квота 100 мб
        }
        self._save_users() # сохранил изменения в файл
        print(f'Пользователь {username} успешно зарегистрирован.')
        return True # регистрация прошла
    
    def login(self, username: str, password: str) -> bool:
        if username in self.users and self.users[username]['password'] == password: # сверил имя и пароль
            self.current_user = username # запомнил кто вошел
            print(f'Добро пожаловать, {username}!')
            return True # вход выполнен
        print('Неверное имя пользователя или пароль.')
        return False # вход не прошел
    
    def logout(self):
        self.current_user = None # сбросил текущего юзера
        print('Вы вышли из системы.')
    
    def get_user_quota(self, username: str) -> int:
        return self.users.get(username, {}).get('total_space', 100 * 1024 * 1024) # вернул квоту юзера или 100 мб
    
    def set_user_quota(self, username: str, quota_mb: int):
        if username in self.users: # проверил есть такой
            self.users[username]['total_space'] = quota_mb * 1024 * 1024 # перевел мб в байты и записал
            self._save_users() # сохранил изменения в файл
            print(f'Квота для {username} установлена: {quota_mb} MB')

class FileManager: #непосредственно файловая система
    def __init__(self, config_path='config.json', user_manager: UserManager = None):
        self.user_manager = user_manager
        self.root_dir = None
        self.current_dir = None
        self._load_config(config_path)
        
    def _load_config(self, config_path): #загрузка файла с настройками
        default_config = {
            'working_directory': './konder'
        }
        if os.path.exists(config_path): #проверил есть ли файл
            with open(config_path, 'r', encoding='utf-8') as f: #открыл на чтение
                self.config = json.load(f) #загрузил настройки
        else:
            self.config = default_config #использовал стандартные настройки
            with open(config_path, 'w', encoding='utf-8') as f: #создал новый файл
                json.dump(default_config, f, indent=2) #записал стандартные настройки
    
    def init_user_workspace(self, username: str): #личная папка для каждого пользователя
        base_dir = Path(self.config.get('working_directory', './konder')).resolve() #где создавать папки для пользователей
        base_dir.mkdir(parents=True, exist_ok=True) #создал базовую папку если её нет
        
        self.root_dir = base_dir / username #путь к личной папке пользователя
        if not self.root_dir.exists():
            self.root_dir.mkdir(parents=True) #создал папку пользователя
        self.current_dir = self.root_dir
        print(f'Рабочая директория: {self.root_dir}')

    def _get_safe_path(self, target_path: str) -> Optional[Path]:
        if not self.root_dir: #проверил инициализацию
            print('Ошибка: Рабочая директория не инициализирована')
            return None
        
        target = Path(target_path) #преобразовал в путь
        if not target.is_absolute(): #если относительный путь
            target = self.current_dir / target #добавил текущую директорию
        
        resolved_target = target.resolve() #получил абсолютный путь
        resolved_root = self.root_dir.resolve() #корень в абсолютном виде
    
        if not str(resolved_target).startswith(str(resolved_root)): #проверил выход за пределы
            print('Ошибка: Выход за пределы рабочей директории запрещен!')
            return None
        
        return resolved_target
    
    def check_quota(self, file_size: int) -> bool:
        if not self.user_manager or not self.user_manager.current_user: #проверил наличие пользователя
            return True
            
        quota = self.user_manager.get_user_quota(self.user_manager.current_user) #получил лимит
        used_space = self._get_directory_size(self.root_dir) #сколько уже занято
        
        if used_space + file_size > quota: #проверил не превысит ли
            print(f'Ошибка: Превышение квоты ({quota // (1024*1024)} MB)')
            return False
        return True
    
    def _get_directory_size(self, path: Path) -> int: #сколько места занимает папка
        total = 0 #обнулил счетчик
        for item in path.rglob('*'): #все внутри папки
            if item.is_file(): #если это файл
                total += item.stat().st_size #прибавил размер
        return total #вернул размер
    
    def draw_panel(self, items: List[Path], title: str = '', width: int = 40): #рисует панель с псевдографикой
        print('+' + '-' * (width - 2) + '+') #верхняя граница
        if title:
            print(f'| {title:<{width-4}} |') #заголовок панели
            print('+' + '-' * (width - 2) + '+') #разделитель
        
        if not items: #если пусто
            print(f'| {"(пусто)":<{width-4}} |')
        else:
            for i, item in enumerate(items[:15]): #ограничил количество
                prefix = 'DIR' if item.is_dir() else 'FILE'
                name = item.name[:width-10] + '...' if len(item.name) > width-10 else item.name
                print(f'| {prefix} {name:<{width-8}} |') #вывел элемент
        
        print('+' + '-' * (width - 2) + '+') #нижняя граница
    
    def ls_gui(self): #показ с псевдографикой
        items = list(self.current_dir.iterdir()) #получил содержимое
        dirs = [item for item in items if item.is_dir()] #только папки
        files = [item for item in items if item.is_file()] #только файлы
        
        dirs.sort(key=lambda x: x.name.lower()) #отсортировал папки
        files.sort(key=lambda x: x.name.lower()) #отсортировал файлы
        self.draw_panel(dirs, 'Папки', 50) #нарисовал папки
        print()
        self.draw_panel(files, 'Файлы', 50) #нарисовал файлы
        self.pwd() #показал путь
    
    def pwd(self): #показ текущей папки
        rel_path = self.current_dir.relative_to(self.root_dir) #относительный путь
        if str(rel_path) == '.': #если точка то пользователь в корне
            path_str = '/' #просто слеш как в проводнике
        else:
            path_str = f'/{rel_path}' #если в папке то слеш спереди
        
        if self.user_manager and self.user_manager.current_user: #если есть менеджер и пользователь залогинился
            used = self._get_directory_size(self.root_dir) #сколько занято
            quota = self.user_manager.get_user_quota(self.user_manager.current_user) #лимит текущего пользователя
            percent = (used / quota) * 100 if quota > 0 else 0 #сколько процентов занято
            print(f'{path_str} [Использовано: {used//1024} KB / {quota//(1024*1024)} MB ({percent}%)]') #вывод статистики
        else:
            print(path_str) #если пользователь не залогинился

    def ls(self): #содержимое текущей папки
        items = list(self.current_dir.iterdir()) #заглянул в текущую папку и составил список
        if not items: #если пусто
            print('пусто!')
            return
        for item in items: #прошелся по содержимому
            prefix = 'DIR' if item.is_dir() else 'FILE'
            print(f'{prefix} {item.name}') #вывел содержимое

    def cd(self, path: str): #переход между папками
        if path == '/': #если в корень
            self.current_dir = self.root_dir #перешел в корень
            return
            
        target = self._get_safe_path(path) #получил путь
        if not target: #если путь неправильный
            return
        if not target.is_dir(): #папка есть но не та
            print(f'Ошибка: {path} не является директорией.')
            return
        self.current_dir = target #перешел в папку

    def mkdir(self, name: str): #создание папки
        target = self._get_safe_path(name) #превратил имя в полный путь
        if not target: #если путь неправильный
            return
        target.mkdir(parents=True, exist_ok=True) #создал папку
        print(f'Директория \'{name}\' создана.')

    def rmdir(self, name: str): #удаление папки
        target = self._get_safe_path(name) #путь к тому что надо удалить
        if not target: #если пути нет
            return
        if not target.is_dir(): #проверил папка ли это
            print(f'Ошибка: {name} не является директорией')
            return
        shutil.rmtree(target) #удалил папку
        print(f'Директория \'{name}\' удалена.')

    def touch(self, name: str): #создание файла
        target = self._get_safe_path(name) #путь для создания
        if not target: #если путь неправильный
            return
        target.touch() #создал файл
        print(f'Файл \'{name}\' создан.')

    def read_file(self, name: str): #чтение файла
        target = self._get_safe_path(name) #получил путь к файлу
        if not target: #если путь неправильный
            return
            
        if target.is_file(): #проверил что это файл
            size = target.stat().st_size #узнал размер
            print(f'FILE {name} (размер: {size} bytes)')
            print('-' * 50) #разделитель
            with open(target, 'r', encoding='utf-8') as f:
                print(f.read()) #вывел содержимое
            print('-' * 50) #разделитель
        else:
            print(f'Ошибка: {name} не является файлом.')

    def write_file(self, name: str, content: str): #запись текста в файл
        target = self._get_safe_path(name) #получил путь к файлу
        if not target: #если путь неправильный
            return
        
        if not self.check_quota(len(content.encode('utf-8'))): #проверка квоты перед записью
            return
            
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content) #записал содержимое
        print(f'Данные записаны в \'{name}\'.')

    def rm(self, name: str): #функция удаления файла
        target = self._get_safe_path(name) #получил путь
        if not target: #если путь неправильный
            return
            
        if target.is_file(): #проверка точно ли это файл
            target.unlink() #удалил файл
            print(f'Файл \'{name}\' удален.')
        else:
            print(f'Ошибка: {name} не является файлом.')

    def cp(self, src: str, dest: str): #копирование файла
        src_path = self._get_safe_path(src) #путь откуда копируем
        dest_path = self._get_safe_path(dest) #путь куда копируем
        
        if not src_path or not dest_path: #проверил пути
            return
        
        if src_path.is_file(): #если это файл
            file_size = src_path.stat().st_size #узнал размер
            if not self.check_quota(file_size): #проверил квоту
                return
                
        shutil.copy2(src_path, dest_path) #скопировал
        print(f'\'{src}\' скопирован в \'{dest}\'.')

    def mv(self, src: str, dest: str): #переместить/переименовать
        src_path = self._get_safe_path(src) #путь к тому что перемещаем
        dest_path = self._get_safe_path(dest) #путь куда перемещаем
        if not src_path or not dest_path: #проверил пути
            return
        shutil.move(src_path, dest_path) #переместил
        print(f'\'{src}\' перемещен/переименован в \'{dest}\'.')
    
    def archive(self, name: str, archive_name: str): #архивация файла или папки
        src_path = self._get_safe_path(name) #путь к тому что архивируем
        archive_path = self._get_safe_path(archive_name) #путь к архиву
        
        if not src_path or not archive_path: #проверил пути
            return
        
        if archive_path.suffix == '.zip': #если zip архив
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if src_path.is_file(): #если файл
                    zipf.write(src_path, src_path.name) #добавил файл
                else: #если папка
                    for root, _, files in os.walk(src_path): #обход всех файлов
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(src_path.parent)
                            zipf.write(file_path, arcname) #добавил файл в архив
        elif archive_path.suffix in ['.tar', '.gz', '.bz2']: #если tar архив
            mode = 'w:' + archive_path.suffix[1:] if archive_path.suffix != '.tar' else 'w'
            with tarfile.open(archive_path, mode) as tar:
                tar.add(src_path, arcname=src_path.name) #добавил в архив
        else:
            print('Ошибка: Неподдерживаемый формат архива. Используйте .zip или .tar')
            return
            
        print(f'\'{name}\' заархивирован в \'{archive_name}\'.')
    
    def extract(self, archive_name: str, dest_dir: str = '.'): #распаковка архива
        archive_path = self._get_safe_path(archive_name) #путь к архиву
        dest_path = self._get_safe_path(dest_dir) #путь куда распаковать
    
        if not archive_path or not dest_path: #проверил пути
            return
    
        if not dest_path.exists(): #если папки нет
            dest_path.mkdir(parents=True) #создал папку
    
        if archive_path.suffix == '.zip': #если zip архив
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                total_size = sum(zinfo.file_size for zinfo in zipf.filelist) #посчитал общий размер
                if not self.check_quota(total_size): #проверил квоту
                    return
                zipf.extractall(dest_path) #распаковал
        elif archive_path.suffix in ['.tar', '.gz', '.bz2']: #если tar архив
            with tarfile.open(archive_path, 'r:*') as tar:
                total_size = sum(member.size for member in tar.getmembers() if member.isfile()) #посчитал размер
                if not self.check_quota(total_size): #проверил квоту
                    return
                tar.extractall(dest_path) #распаковал
        else:
            print('Ошибка: Неподдерживаемый формат архива.')
            return
        
        print(f'\'{archive_name}\' распакован в \'{dest_dir}\'.')
    
    def quota(self, username: str = None, new_quota: int = None): #показать квоту и изменить квоту
        if not self.user_manager: #есть ли менеджер пользователей
            print('Менеджер пользователей не активен.')
            return  
        target_user = username if username else self.user_manager.current_user #определил текущего пользователя
        
        if not target_user: #если пользователь не определен
            print('Пользователь не указан')
            return
        
        if new_quota: #проверка на новую квоту
            self.user_manager.set_user_quota(target_user, new_quota) #установил новую квоту
        else: #когда не нужно менять квоту а просто посмотреть
            quota = self.user_manager.get_user_quota(target_user) #сколько выделено пользователю
            used = self._get_directory_size(self.root_dir) if self.root_dir else 0 #сколько занято
            print(f'Пользователь: {target_user}') #имя
            print(f'Квота: {quota // (1024*1024)} MB') #печать лимита
            if quota > 0:
                print(f'Использовано: {used // (1024*1024)} MB ({used/quota*100}%)') #сколько свободно


def print_help(): #вывод справки
    print('''
ФАЙЛОВЫЙ МЕНЕДЖЕР - СПРАВКА

Основные команды:
  pwd                    (показать текущую директорию)
  ls                     (показать содержимое обычный режим)
  ls gui                 (показать содержимое псевдографика)
  cd <путь>              (перейти в директорию)
  cd /                   (перейти в корень)

Работа с файлами:
  touch <имя>            (создать пустой файл)
  read <имя>             (прочитать файл)
  write <имя> <текст>    (записать текст в файл)
  rm <имя>               (удалить файл)
  cp <откуда> <куда>     (скопировать файл)
  mv <откуда> <куда>     (переместить или переименовать)

Работа с папками:
  mkdir <имя>            (создать папку)
  rmdir <имя>            (удалить папку)

Архивация:
  archive <имя> <архив>  (заархивировать zip или tar)
  extract <архив> [путь] (распаковать)

Пользователи:
  register <имя> <пароль> (регистрация)
  login <имя> <пароль>    (вход)
  logout                  (выход)
  quota [имя] [нов_квота] (просмотр или изменение квоты)

  help                    (показать эту справку)
  exit                    (выход)
''')

# Основная программа
if __name__ == '__main__':
    os.makedirs('./konder', exist_ok=True) #создал папку для файлов
    
    user_manager = UserManager() #создал менеджер пользователей
    fm = FileManager(user_manager=user_manager) #создал файловый менеджер
    
    print('ФАЙЛОВЫЙ МЕНЕДЖЕР')
    
    while True:
        if not user_manager.current_user: #если пользователь не вошел
            print('1. Вход')
            print('2. Регистрация')
            print('3. Выход')
            
            choice = input('Выберите действие: ').strip()
            
            if choice == '1': #вход
                username = input('Имя пользователя: ').strip()
                password = getpass.getpass('Пароль: ')
                if user_manager.login(username, password): #проверил логин
                    fm.init_user_workspace(username) #создал рабочую папку
            elif choice == '2': #регистрация
                username = input('Имя пользователя: ').strip()
                password = getpass.getpass('Пароль: ')
                if user_manager.register(username, password): #зарегистрировал
                    if user_manager.login(username, password): #вошел
                        fm.init_user_workspace(username) #создал рабочую папку
            elif choice == '3': #выход
                print('До свидания!')
                break
            continue
        
        try:
            rel_path = fm.current_dir.relative_to(fm.root_dir) #относительный путь
            if str(rel_path) == '.': #если в корне
                prompt = f'[{user_manager.current_user}@FM:/] > '
            else:
                prompt = f'[{user_manager.current_user}@FM:/{rel_path}] > '
        except:
            prompt = f'[{user_manager.current_user}@FM] > '
        
        command_line = input(prompt).strip() #получил команду
        if not command_line: #если пусто
            continue
        
        args = shlex.split(command_line) #разобрал команду
        cmd = args[0].lower() #первое слово - команда

        if cmd == 'exit': #выход
            print('Завершение работы.')
            break
        elif cmd == 'help': #справка
            print_help()
        elif cmd == 'logout': #выход из аккаунта
            user_manager.logout()
            fm.root_dir = None
            fm.current_dir = None
        elif cmd == 'pwd': #текущая папка
            fm.pwd()
        elif cmd == 'ls': #список файлов
            if len(args) > 1 and args[1] == 'gui': #с графикой
                fm.ls_gui()
            else: #обычный
                fm.ls()
        elif cmd == 'cd' and len(args) == 2: #переход
            fm.cd(args[1])
        elif cmd == 'mkdir' and len(args) == 2: #создать папку
            fm.mkdir(args[1])
        elif cmd == 'rmdir' and len(args) == 2: #удалить папку
            fm.rmdir(args[1])
        elif cmd == 'touch' and len(args) == 2: #создать файл
            fm.touch(args[1])
        elif cmd == 'read' and len(args) == 2: #прочитать файл
            fm.read_file(args[1])
        elif cmd == 'write' and len(args) >= 3: #записать в файл
            text = ' '.join(args[2:])
            fm.write_file(args[1], text)
        elif cmd == 'rm' and len(args) == 2: #удалить файл
            fm.rm(args[1])
        elif cmd == 'cp' and len(args) == 3: #копировать
            fm.cp(args[1], args[2])
        elif cmd == 'mv' and len(args) == 3: #переместить
            fm.mv(args[1], args[2])
        elif cmd == 'archive' and len(args) == 3: #архивировать
            fm.archive(args[1], args[2])
        elif cmd == 'extract' and len(args) in [2, 3]: #распаковать
            dest = args[2] if len(args) == 3 else '.'
            fm.extract(args[1], dest)
        elif cmd == 'quota': #квота
            if len(args) == 3: #изменить квоту
                try:
                    fm.quota(args[1], int(args[2]))
                except ValueError:
                    print('Ошибка: квота должна быть числом')
            elif len(args) == 2: #посмотреть квоту другого
                fm.quota(args[1])
            else: #посмотреть свою
                fm.quota()
        elif cmd: #неизвестная команда
            print('Неизвестная команда или неверное количество аргументов. Введите help.')