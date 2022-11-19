'''
NAS_search: Поиск файлов в хранилище по списку
'''
import glob as gl
import os, sys
from datetime import datetime


def convert_bytes(num):
    """
    Converts bytes to MB.... GB... etc
    """
    for x in ['bytes', 'K', 'M', 'G', 'T']:
        if num < 1024.0:
            return f'{num:3.1f}{x}'
        num /= 1024.0


def file_to_list(file: str):
    """
    Reads text file and returns list of strings
    """
    if os.path.isfile(file):
        with open(file, 'r', encoding='utf-8') as f:
            list = [x.strip() for x in f]
        return list
    else:
        raise FileNotFoundError(f'Файл {file} не найден.')


# def nas(path='Z:\\**\\*.mp4', file_name='nas.txt', save_file=False):
def nas(path='C:\\Users\\ALeX\\Documents\\Python\\**\\*.mp4', file_name='nas.txt', save_file=False):
    start_time = datetime.now()
    print('Поиск файлов на NAS...')
    paths = gl.glob(path, recursive=True)
    time = datetime.now() - start_time
    print(f"Поиск завершен ({time}), всего {len(paths)} файлов")
    if save_file:
        with open(file_name, 'w', encoding="utf-8") as file:
            for item in paths:
                file.write(item + "\n")
    return paths


def arg_check(arg, n):
    if len(sys.argv) > n:
        if sys.argv[n] == arg:
            return True
        else:
            return False
    else:
        return False


def main():
    if arg_check('--scan', 1):
        nas(save_file=True)
    films = file_to_list('1.txt')
    paths = file_to_list('nas.txt')
    file_names = [os.path.splitext(os.path.basename(x))[0] for x in paths]
    films_not_found = []
    for film in films:
        flag = False
        for j, file_name in enumerate(file_names):
            if file_name.lower().find(film.lower()) != -1:
                print(f"{film:25} {paths[j]:70} {convert_bytes(os.path.getsize(paths[j]))}")
                flag = True
        if not flag:
            films_not_found.append(film)
    print(f"\nНе найдены ({len(films_not_found)}):\n" + "\n".join(films_not_found))


if __name__ == '__main__':
    main()
