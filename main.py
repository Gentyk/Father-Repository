def move(array, cell1, cell2, n_order, quality=None):
    pass

def move_left(array, cell1, cell2, delta):
    pass

def move_right(array, cell1, cell2, delta, quality=None):
    pass


def engines_quality(local_orders):
    """ Подсчет количества двигателей, которые планировалось произвести за неделю

    :param local_orders: массив вида
            [
                {номер заказа, количество двигателей},
                ...
            ]
    :return: суммарное количество двигателей для всех заказов в массиве
    """
    result = 0
    for _, quality in local_orders:
        result += quality
    return result


def normalize(orders, differences):
    n = len(orders)
    for i in range(n):
        if differences[i] > 0:
            pass
        elif differences[i] < 0:
            # случай, когда отстаем от плана и надо искать производства справа
            #
            # в таком случае мы просто перемещаем необходимое количество заказов в правостоящую ячейку
            j = i + 1
            sum_ = engines_quality(orders[j])
            move_right(orders, i, j, differences[i], sum_)
            differences[j] += differences[i]
            differences[i] = 0



