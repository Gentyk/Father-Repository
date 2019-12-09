from collections import OrderedDict
import pandas as pd
import logging
import datetime

from default import date_


class Record:

    def __init__(self, differences: list, orders: list):
        if sum(differences) != 0:
            raise Exception(f"Sum differences != 0: {differences}")
        self.differences = differences
        self.orders = orders

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
            self.orders[cell_to][order_name]= quality

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
            if delta > from_local_order[order_name]:
                delta -= from_local_order[order_name]
                self.move(cell_from, cell_to, order_name)
                print(cell_from, cell_to, order_name)
            else:
                self.move(cell_from, cell_to, order_name, delta)
                print(cell_from, cell_to, order_name, delta)
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
        from_local_order = self.orders[cell_from]
        order_names = from_local_order.keys()
        # порядок перемещения - начинаем с более старых заказов
        order_names = list(order_names)[::-1]
        for order_name in order_names:
            # логгирование
            if quality and quality > 0:
                if quality > from_local_order[order_name]:
                    pass
                else:
                    quality = 0
                    pass

            # перемещение
            if delta > from_local_order[order_name]:
                delta -= from_local_order[order_name]
                self.move(cell_from, cell_to, order_name)
                print(cell_from, cell_to, order_name)
            else:
                self.move(cell_from, cell_to, order_name, delta)
                print(cell_from, cell_to, order_name, delta)
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
                    if self.orders[j] is not {}:
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
                sum_ = sum(self.orders[j])
                self.move_right(i, j, -self.differences[i], sum_)
                self.differences[j] += self.differences[i]
                self.differences[i] = 0


def get_index_week(row, date_df):

    keys = row.keys()
    keys = [int(key[2:]) for key in keys if key.startswith('Gr')]
    keys.sort()
    index_week = {keys[i]: i for i in range(len(keys))}
    # print(keys)
    # print(date_df['т'])
    #
    date_df['datetime'] = date_df['тт'].apply(lambda x: datetime.date(x.year, x.month, x.day))
    # for i in range(len(keys)):
    #     print(date_df['datetime'].get(i), date_[keys[i]], date_df['datetime'].get(i) == date_[keys[i]])
    #     gg = date_df.loc[date_df['datetime'] == date_[keys[i]]]
    #     print(gg.get('тт').values[0])
    index_date = {date_df.loc[date_df['т'] == keys[i]].get('datetime').values[0]: i for i in range(len(keys))}
    # for k, v in index_date.items():
    #     print(type(k), k, v)
    return index_week, index_date


def get_record(row, order_df, index_week, index_date):
    """ Производит анализ одной строки планирования

    Переносы фиксируются в необходимые файлы

    :param row: pandas.Series - одна строка таблицы планирования
    :param order_df: pandas.DataFrame - таблица заказов
    """
    # сначала сформируем массив несостыковки планов и графиков
    differences = [0 for _ in range(len(index_week))]
    for k in row.keys():
        if k.startswith("Gr") and row[k]:
            differences[index_week[int(k[2:])]] += int(row[k])
        if k.startswith("Pl") and row[k]:
            differences[index_week[int(k[2:])]] -= int(row[k])
    print(differences)

    orders = [{} for _ in range(len(index_week))]
    local_order_df = order_df.loc[order_df['Id_125'] == row[' ID_125 ']]
   # local_order_df['datetime'] = local_order_df['Дата кон.'].apply(lambda x: datetime.date(x.year, x.month, x.day))
    for ind, local_row in local_order_df.iterrows():
        order = local_row['Заказ']
        date = local_row['datetime']
        number_of_engines = local_row['План']
        # print(type(pd.to_datetime(date)))
        # print(index_date[date], date)
        orders[index_date[date]][order] = number_of_engines
    # for i in orders:
    #     print(i)
    record = Record(differences, orders)
    record.normalize()



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
            # print(sum_)
            # print(row)
            error_indexes.append(index)
    if error_indexes:
        raise Exception(f"Таблица планирования неверна: в строках {error_indexes} нестыковки по графику и плану "
                        f"разнятся.")


def main():
    filename = "123.xls"
    order_sheet = "дано"
    schedule_sheet = "ориг"
    date_sheet = "Лист0"
    xl = pd.ExcelFile(filename)
    order_df = xl.parse(order_sheet, skiprows=2)
    order_df['datetime'] = order_df['Дата кон.'].apply(lambda x: datetime.date(x.year, x.month, x.day))
    date_df = xl.parse(date_sheet)
    schedule_df = xl.parse(schedule_sheet, skiprows=1)
    schedule_df = schedule_df.fillna(0)     # заполнили пробелы ноликами
    check_schedule_table(schedule_df)
    index_week, index_date = None, None
    for index, row in schedule_df.iterrows():
        if index_date is None:
            index_week, index_date = get_index_week(row, date_df)

        get_record(row, order_df, index_week, index_date)
        #break

if __name__ == "__main__":
    main()


