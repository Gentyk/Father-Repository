# -*- coding: utf-8 -*-
import codecs
import configparser
import datetime
from collections import OrderedDict

import pandas as pd


class Record:

    def __init__(self, engine_id, differences: list, orders: list, index_date: dict, order_dict: dict):
        if sum(differences) != 0:
            raise Exception(f"Sum differences != 0: {differences}")
        self.engine_id = engine_id
        self.differences = differences
        for i in range(len(differences)):
            if differences[i] < 0 and -differences[i] > sum(orders[i].values()):
                raise Exception(f"План расходится с заказом на детали {engine_id}.")
        self.orders = [Record.sort_orders(week_order) for week_order in orders]
        self.index_date = index_date    # соответсвие индекса массива определенной дате
        self.order_dict = order_dict    # то , что было на старте:
        self.move_to_future = {}

        # табличка для логирования случаев, когда переносим весь заказ
        columns = ['Id_125', 'План', 'вн/внутр', 'Заказ', 'Дата кон.', 'd+']
        self.transfers_without_separation = pd.DataFrame(columns=columns)
        # табличка для логирования случаев, когда переносим часть заказа
        columns2 = ['Id_125', 'Заказ', 'Всего в заказе', 'Дата кон.', 'План', 'd+']
        self.transfers_with_separation = pd.DataFrame(columns=columns2)

    @staticmethod
    def sort_orders(one_week_orders):
        """ сортируем заказы на одну неделю в порядке возрастания двух номеров
        """
        keys = list(one_week_orders.keys())
        keys.sort(key=lambda x: (x[0], x[1], x[2]))
        new_dict = OrderedDict()
        for k in keys:
            new_dict[k] = one_week_orders[k]
        return new_dict

    def move(self, cell_from, cell_to, order_name, quality=None):
        """ Перемещение некоторого количества двигаетелей определенного заказа из одной ячейки массива orders в другую
        Другими словами - перемещение партии двигателей из заказа n_order с одной недели на другую
        :param cell_from: номер ячейки, из которой мы будем перемещать некоторое количество двигателей
        :param cell2: номер ячейки, в которую мы будем перемещать некоторое эти двигатели
        :param order_name: имя заказа
        :param quality: если мы перемещаем не весь заказ, а несколько деталей, то надо указать это количество. Если
                        перемещаем весь заказ, то параметр не указываем
        """
        if not quality or isinstance(quality, int) and quality == self.orders[cell_from][order_name]:
            quality = self.orders[cell_from].pop(order_name)
        else:
            self.orders[cell_from][order_name] -= quality
        if order_name in self.orders[cell_to]:
            self.orders[cell_to][order_name] += quality
        else:
            self.orders[cell_to][order_name] = quality

        self.orders[cell_to] = Record.sort_orders(self.orders[cell_to])

    def move_left(self, cell_from: int, cell_to: int, delta:int):
        """ Перемещение заказов на более ранние недели с отметкой этого в журнале
        Заказы перебираются в порядке. Ячейка cell_to стоит левее ячейки cell_from, а значит её номер меньше,
        чем у ячейки cell_from. delta должна быть меньше, чем сумма всех двигателей в заказах на cell_from неделю.
        :param cell_from: из какой ячейки переносим
        :param cell_to: в какую ячейку переносим
        :param delta: количество двигателей(это может быть не один заказ, а много), которое хотим переместить
        """
        if cell_from <= cell_to:
            raise Exception(f"Ошибка в порядке перемещения move_left: {cell_from} <= {cell_to}")
        if sum(self.orders[cell_from].values()) < delta:
            raise Exception(f"Ошибка в порядке перемещения move_left: delta ({delta}) > {sum(self.orders[cell_from].values())}")
        from_local_order = self.orders[cell_from].copy()
        order_names = from_local_order.keys()
        for order_name in order_names:
            if delta >= from_local_order[order_name]:
                delta -= from_local_order[order_name]
                self.move(cell_from, cell_to, order_name)
                # print(cell_from, cell_to, order_name)
                t = self.transfers_with_separation[self.transfers_with_separation['Заказ'] == order_name]
                if not t.empty:
                    # в случаях, когда заказ хоть раз уже был перенесене на другие даты дробно, то необходимо указать количество для переноса,
                    # чтобы данный перенос был также записан в дробную таблицу
                    self.mark_transition(order_name, cell_from, cell_to, from_local_order[order_name])
                else:
                    self.mark_transition(order_name, cell_from, cell_to)
                if delta == 0:
                    break
            else:
                self.move(cell_from, cell_to, order_name, delta)
                # print(cell_from, cell_to, order_name, delta)
                self.mark_transition(order_name, cell_from, cell_to, delta)
                break

    def move_right(self, cell_from: int, cell_to: int, delta: int, quality=None):
        """ Перемещение заказа на последующие недели (после срока)  с отметкой этого в журнале
        :param cell_from: из какой ячейки переносим
        :param cell_to: в какую ячейку переносим
        :param delta: количество двигателей(это может быть не один заказ, а много), которое хотим переместить
        :param quality: сколько двигателей надо залогировать (по умолчанию - все перенесенные)
        """
        if cell_from >= cell_to:
            raise Exception(f"Ошибка в порядке перемещения move_right: {cell_from} >= {cell_to}")
        from_local_order = Record.sort_orders(self.orders[cell_from])
        order_names = from_local_order.keys()
        # порядок перемещения - начинаем с более старых заказов
        order_names = list(order_names)[::-1]
        for order_name in order_names:
            if order_name not in self.move_to_future:
                self.move_to_future[order_name] = [cell_from, None]

            # перемещение
            if delta >= from_local_order[order_name]:
                delta -= from_local_order[order_name]
                self.move(cell_from, cell_to, order_name)
                self.mark_transition(order_name, cell_from, cell_to)
                if delta == 0:
                    break

            else:
                self.move_to_future[order_name][1] = True
                self.move(cell_from, cell_to, order_name, delta)
                self.mark_transition(order_name, cell_from, cell_to, delta)
                break

    def normalize(self):
        """ Обработка одной строки
        """
        n = len(self.orders)
        for i in range(n):
            if self.differences[i] > 0:
                # Если по графику мы опережаем (Gr>0, PL=0)
                j = i + 1
                while self.differences[i] != 0:
                    if self.orders[j]:
                        week_sum = sum(self.orders[j].values())
                        if week_sum >= self.differences[i]:
                            self.move_left(j, i, self.differences[i])
                            self.differences[j] += self.differences[i]
                            self.differences[i] = 0
                        else:
                            self.move_left(j, i, week_sum)
                            self.differences[j] += week_sum
                            self.differences[i] -= week_sum
                            j += 1
                    else:
                        j += 1
            elif self.differences[i] < 0:
                # случай, когда отстаем от плана и надо искать производства справа
                #
                # в таком случае мы просто перемещаем необходимое количество заказов в правостоящую ячейку
                j = i + 1
                sum_ = sum(self.orders[j].values()) if self.orders[j] else 0
                quality = min(-self.differences[i], sum_) if sum_ else sum_
                if self.differences[j] > quality:
                    quality = self.differences[j]
                self.move_right(i, j, -self.differences[i], quality)
                self.differences[j] += self.differences[i]
                self.differences[i] = 0

    def mark_transition(self, order_name: str, cell_from: int, cell_to: int, quality: int=None):
        """ Записываем в таблички что и куда перенесли"""
        data = {
            'Id_125': self.engine_id,
            'План': self.order_dict[order_name][0],
            'вн/внутр': self.order_dict[order_name][1],
            'Заказ': order_name,
            'Дата кон.': self.index_date[cell_from],
            'd+': self.index_date[cell_to],
        }
        if not quality:
            # переносим весь заказ
            # если он уже был
            t = self.transfers_without_separation[
                (self.transfers_without_separation['Id_125'] == self.engine_id) &
                (self.transfers_without_separation['План'] == self.order_dict[order_name][0]) &
                (self.transfers_without_separation['Заказ'] == order_name) &
                (self.transfers_without_separation['d+'] == self.index_date[cell_from])
            ]
            if not t.empty:
                self.transfers_without_separation.loc[t.index, 'd+'] = self.index_date[cell_to]
            else:
                # если еще не было, то оставляем исходные данные
                self.transfers_without_separation = self.transfers_without_separation.append(
                    data.copy(),
                    ignore_index=True
                )
        # переносим часть
        else:
            del data['вн/внутр']
            data['План'] = quality
            data['Всего в заказе'] = self.order_dict[order_name][0]
            # сначала проверяем в целых
            # если найдем, то удаляем оттуда,
            # запомнив начальную дату и создав две записи
            t = self.transfers_without_separation[
                (self.transfers_without_separation['Id_125'] == self.engine_id) &
                (self.transfers_without_separation['План'] == self.order_dict[order_name][0]) &
                (self.transfers_without_separation['Заказ'] == order_name) &
                (self.transfers_without_separation['d+'] == self.index_date[cell_from])
            ]
            if not t.empty:
                # преобразуем запись из таблицы без делений
                local_data = t.to_dict(orient='records')[0]
                local_data['План'] = local_data['План'] - data['План']
                del local_data['вн/внутр']
                data['План'] = quality
                local_data['Всего в заказе'] = self.order_dict[order_name][0]
                # удаляем запись
                self.transfers_without_separation = self.transfers_without_separation.loc[
                    ~(self.transfers_without_separation['Id_125'] == self.engine_id) |
                    ~(self.transfers_without_separation['План'] == self.order_dict[order_name][0]) |
                    ~(self.transfers_without_separation['Заказ'] == order_name) |
                    ~(self.transfers_without_separation['d+'] == self.index_date[cell_from])
                ]
                # записываем в таблицу делений
                self.transfers_with_separation = self.transfers_with_separation.append(
                    local_data.copy(),
                    ignore_index=True
                )

                data['Дата кон.'] = local_data['Дата кон.']
                self.transfers_with_separation = self.transfers_with_separation.append(
                    data.copy(),
                    ignore_index=True
                )
            else:
                # если в целочисленной части нету, то ищем в дробной
                t = self.transfers_with_separation[
                    (self.transfers_with_separation['Id_125'] == self.engine_id) &
                    (self.transfers_with_separation['Заказ'] == order_name) &
                    (self.transfers_with_separation['d+'] == self.index_date[cell_from])
                    ]
                if t.empty:
                    # если такой записи не было, то пишем с нуля
                    self.transfers_with_separation = self.transfers_with_separation.append(
                        data.copy(),
                        ignore_index=True
                    )
                elif int(t['План']) == quality:
                    # в случае полного совпадения  - переносим дату
                    self.transfers_with_separation.loc[t.index, 'd+'] = self.index_date[cell_to]
                else:
                    local_delta = self.transfers_with_separation['План'] - quality
                    data['Дата кон.'] = t.to_dict(orient='records')[0]['Дата кон.']
                    self.transfers_with_separation.loc[t.index, 'План'] = local_delta
                    self.transfers_with_separation = self.transfers_with_separation.append(
                        data.copy(),
                        ignore_index=True
                    )


def get_index_week(row, date_df):
    """ Возвращает словари соответсвия дат и индексов будущих таблиц
    Рассматривая каждое издение, будут созданы массивы каждый элемент которых соответствует отстованию от плана
    на неделю или содержит список заказов на определенной неделе. Для того, чтобы не потерять соответствие дат и
    индексов массивов ввожу дополнительные словари соответствия.
    index_date - словарь , где каждому индексу соответствует дата
        например,
        {
            '01.03.2019': 0,
            '07.03.2019': 1,
            ...
        }
    index_week - аналогично, но только с номерами недели
        например,
        {
            9: 0,
            10: 1,
            ...
        }
    """
    keys = row.keys()
    keys = [int(key[2:]) for key in keys if key.startswith('Gr')]
    keys.sort()
    index_week = {keys[i]: i for i in range(len(keys))}

    date_df['datetime'] = date_df['тт'].apply(lambda x: datetime.date(x.year, x.month, x.day))
    index_date = {date_df.loc[date_df['т'] == keys[i]].get('datetime').values[0]: i for i in range(len(keys))}
    return index_week, index_date


def get_order_keys(key):
    """ сортируем заказы на одну неделю в порядке возрастания двух номеров
    """
    num1 = 0
    x = key.split('*')
    str1 = x[0]
    n = len(str1)
    for i in range(n):
        try:
            local_num = int(str1[n - i - 1])
            num1 += local_num * 10 ** i
        except:
            break

    # получаем второе число
    num2 = 0
    if len(x) > 1:
        x = key.split('-')
        if len(x) > 1:
            str2 = x[-1]
            try:
                local_num = int(str2.split('/')[0])
                num2 += local_num
            except:
                pass
    return num1, num2



def get_record(row, order_df, index_week, index_date, conf_file='config.ini'):
    """ Производит анализ одной строки планирования
    Переносы фиксируются в необходимые файлы
    :param row: pandas.Series - одна строка таблицы планирования
    :param order_df: pandas.DataFrame - таблица заказов
    :param index_week: соответсвие индексов номерам недель
    :param index_date: соответсвие индексов пятницам(дням)
    :param conf_file: имя конфиг файла. необходим для более информативного вывода ошибок.
    :return: pandas.DataFrame - таблица перенесенных заказов без разделения
             pandas.DataFrame - таблица перенесенных заказов, когда произошло разделение
    """
    # сначала сформируем массив несостыковки планов и графиков
    differences = [0 for _ in range(len(index_week))]
    for k in row.keys():
        if k.startswith("Gr") and row[k]:
            differences[index_week[int(k[2:])]] += int(row[k])
        if k.startswith("Pl") and row[k]:
            differences[index_week[int(k[2:])]] -= int(row[k])
    #print(differences)

    # формируем массив заказов
    orders = [{} for _ in range(len(index_week))]
    engine_id = row['ID_125']
    local_order_df = order_df.loc[order_df['Id_125'] == engine_id]
    local_order_dict = {}
    order_types = {}
    order_ids = {}
    k = 10000
    for ind, local_row in local_order_df.iterrows():
        order = local_row['Заказ']
        num1, num2 = get_order_keys(order)
        key = (num1, num2, k)
        k -= 1
        date = local_row['datetime']
        number_of_engines = local_row['План']
        if date not in index_date:
            config = configparser.ConfigParser()
            config.read_file(codecs.open(conf_file, "r", "utf8"))
            ord_name = local_row['Наименование'].strip()
            raise Exception(f"Дата кон. \'{date.strftime('%d.%m.%Y')}\' заказа {order} (наименование \'{ord_name}\') "
                            f"отсутствует в таблице дат (даты находятся на вкладке {config['DEFAULT']['date_sheet']}).")
        orders[index_date[date]][key] = number_of_engines

        # замена имен заказов на id вида <номер элемента массива>ххх
        # другими словами, генерация словаря вида {id1: name1, id2: name2, ...} (имена могут повторяться)
        order_ids[key] = order
        local_order_dict[key] = [number_of_engines, local_row['вн/внутр']]


    invert_index_date = {v: k for k, v in index_date.items()}

    record = Record(engine_id, differences, orders, invert_index_date, local_order_dict)
    record.normalize()

    # замена id на имена заказов в результирующей таблице
    def key_to_name(row):
        key = row['Заказ']
        if key in order_ids:
            row['Заказ'] = order_ids[key]
        return row

    transfers_without_separation = record.transfers_without_separation
    transfers_without_separation = transfers_without_separation.apply(key_to_name, axis=1)
    transfers_with_separation = record.transfers_with_separation
    transfers_with_separation = transfers_with_separation.apply(key_to_name, axis=1)

    return transfers_without_separation, transfers_with_separation


def check_schedule_table(schedule_df):
    """ Проверка, что в таблице планирования нету ошибки
    если сумма чисел под Gr* не равна сумме чисел под PL*, то выдастся соответствующая ошибка
    """
    error_indexes = []
    for index, row in schedule_df.iterrows():
        sum_ = 0
        for k in row.keys():
            if k.startswith("Gr") and row[k]:
                sum_ += row[k]
            if k.startswith("Pl") and row[k]:
                sum_ -= row[k]
        if sum_ != 0:
            error_indexes.append(index)
    if error_indexes:
        raise Exception(f"Таблица планирования неверна: в строках {error_indexes} нестыковки по графику и плану "
                        f"разнятся.")


def features_to_numbers(row):
    """ Преобразует значение поля 'вн/внутр' в соответствующее число
    param: row - строка таблицы dataframe
    return: преобразованная строка
    """
    if not isinstance(row['вн/внутр'], str):
        if isinstance(row['вн/внутр'], int) and row['вн/внутр'] in [1, 2]:
            return row
        else:
            t = type(row['вн/внутр'])
            raise Exception(f"Ошибка при обработке столбца \'вн/внутр\' заказа {row['Заказа']}. "
                            f"Значение {row['вн/внутр']}, тип {t}.")
    s = row['вн/внутр'].strip()
    row['вн/внутр'] = 1 if 'внешний' == s else 2
    return row


def get_tables(conf_file='config.ini'):
    """ Получение и минимальное форматирование стартовых таблиц
    Обрезаем лишние пробелы справа и слева в именах столбцов
    :param conf_file: имя конфиг файла
    :return: order_df - большая таблица заказов с заменой "вн/внутр" на числа,
             schedule_df - таблица плана (пустоты заполнены нулями),
             date_df - таблица дат буз изменений,
             order_type - просто запоминает "вн/внутр" для каждого заказа
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(conf_file, "r", "utf8"))
    def_section = config['DEFAULT']
    xl = pd.ExcelFile(def_section['filepath'])

    # большая таблица заказов
    order_df = xl.parse(def_section['order_sheet'], skiprows=2)
    order_df['datetime'] = order_df['Дата кон.'].apply(lambda x: datetime.date(x.year, x.month, x.day))

    # даты
    date_df = xl.parse(def_section['date_sheet'])

    # таблица планирования
    schedule_df = xl.parse(def_section['schedule_sheet'], skiprows=1)
    schedule_df = schedule_df.fillna(0)     # заполнили пробелы ноликами
    check_schedule_table(schedule_df)
    xl.close()

    # обрезаем лишние пробелы у столбцов, чтобы не было проблем при обращении по именам
    for datafr in [order_df, schedule_df, date_df]:
        columns = {i: i.strip() for i in list(datafr.columns) if i != i.strip()}
        if columns:
            print(columns)
            datafr = datafr.rename(columns=columns, inplace=True)

    # преобразуем все значения столбца вн/внутр в числа
    order_df = order_df.apply(features_to_numbers, axis=1)

    # словарь вн/внутр для заказов
    unique_orders_names = order_df['Заказ'].unique()
    order_type = {}
    for name in unique_orders_names:
        order_type[name] = order_df[order_df['Заказ'] == name]['вн/внутр'].values[0]

    return order_df, schedule_df, date_df, order_type


def split_into_iterations(df_separation, order_types) -> (list, pd.DataFrame):
    """ Разделим результат (разделяющиеся заказы) на итерации в случае, если в результатах заказ делился несколько раз
    """
    iterations = []
    second_integer_order_df = pd.DataFrame(columns=['Id_125', 'План', 'вн/внутр', 'Заказ', 'Дата кон.', 'd+'])
    select_columns = ['Id_125', 'Заказ', 'Всего в заказе', 'Дата кон.']
    columns2 = ['Id_125', 'Заказ', 'Всего в заказе', 'Дата кон.', 'План', 'd+']
    orders = {}
    for row in df_separation.to_dict(orient='records'):
        keys = str({k: v for k, v in row.items() if k in select_columns})
        if keys in orders:
            index = orders[keys][0]
            number_of_engines = orders[keys][1]
            update_row = row.copy()
            update_row['Всего в заказе'] -= number_of_engines
            while len(iterations) < index + 1 and update_row['Всего в заказе'] != update_row['План']:
                iterations.append(pd.DataFrame(columns=columns2))
            if update_row['Всего в заказе'] != update_row['План']:
                iterations[index] = iterations[index].append(
                    update_row.copy(),
                    ignore_index=True
                )
                orders[keys] = [index + 1, number_of_engines + row['План']]
            else:
                del update_row['Всего в заказе']
                update_row['вн/внутр'] = order_types[update_row['Заказ']]
                second_integer_order_df = second_integer_order_df.append(
                    update_row.copy(),
                    ignore_index=True
                )
                orders[keys][1] = number_of_engines + row['План']
        else:
            if not iterations:
                iterations.append(pd.DataFrame(columns=columns2))
            update_row = row.copy()
            if update_row['Всего в заказе'] != update_row['План']:
                iterations[0] = iterations[0].append(
                    update_row.copy(),
                    ignore_index=True
                )
                orders[keys] = [1, row['План']]
            else:
                del update_row['Всего в заказе']
                update_row['вн/внутр'] = order_types[update_row['Заказ']]
                second_integer_order_df = second_integer_order_df.append(
                    update_row.copy(),
                    ignore_index=True
                )
                orders[keys] = [0, row['План']]
    return iterations, second_integer_order_df


def write_to_file(df_, df_separation, order_types, conf_file='config.ini'):
    """ Запись в файл
    :param df_: таблица для случаев, когда заказ переносится полностью
    :param df_separation: таблица для случаев, когда заказ переносится частично
    :param order_types: словарь вида {заказ: "вн/внешн" этого заказа в виде числа}
    :param conf_file: имя кофиг файлы - для именования выходного файла и стобцов в нем
    """
    config = configparser.ConfigParser()
    config.read_file(codecs.open(conf_file, "r", "utf8"))
    def_section = config['DEFAULT']
    df_separation_list, second_integer_order_df = split_into_iterations(df_separation, order_types)
    with pd.ExcelWriter(def_section['result_filepath'], engine='xlsxwriter', date_format='dd.mm.yyyy') as writer:
        df_.to_excel(writer, sheet_name=def_section['result_sheet'], index=False)
        if not second_integer_order_df.empty:
            second_integer_order_df.to_excel(writer, sheet_name='res_2', index=False)
        for i, df_sep in enumerate(df_separation_list):
            sheet_name = def_section['result_separation_sheet'] + f"(iter-{i})"
            df_sep.to_excel(writer, sheet_name=sheet_name, index=False)
        writer.save()


def main():
    order_df, schedule_df, date_df, order_type = get_tables()
    result_table = pd.DataFrame()
    result_table_with_separation = pd.DataFrame()
    index_week, index_date = None, None
    for index, row in schedule_df.iterrows():

        if index_date is None:
            index_week, index_date = get_index_week(row, date_df)

        res_df, res_df_with_separation = get_record(row, order_df, index_week, index_date)
        result_table = result_table.append(res_df.copy())
        result_table_with_separation = result_table_with_separation.append(res_df_with_separation.copy())

    write_to_file(result_table, result_table_with_separation, order_type)


if __name__ == "__main__":
    main()
