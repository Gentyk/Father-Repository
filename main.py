from collections import OrderedDict
import logging


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
            self.orders[cell_to] += quality
        else:
            self.orders[cell_to] = quality

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
        from_local_order = self.orders[cell_from]
        order_names = from_local_order.keys()
        for order_name in order_names:
            if delta > from_local_order[order_name]:
                delta -= from_local_order[order_name]
                self.move(cell_from, cell_to, order_name)
            else:
                self.move(cell_from, cell_to, order_name, delta)
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
        order_names = order_names[::-1]
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
            else:
                self.move(cell_from, cell_to, order_name, delta)
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
                    if self.orders[j] is None:
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



