with open("all_data.txt",'r') as f:
    lines = f.readlines()


def avg(v):
    if v:
        return sum(v) / len(v)
    else:
        return 0


def values(_drop, _corrupt, _mode, var):
    to_return = []
    for line in lines:
        if line.split():
            mode, drop, corrupt, role, ack_rec, acks_sent, frames_trans, dup_rec, \
            retrans, time = line.split()

            if _drop == drop and _corrupt == corrupt and _mode == mode:
                if var == "ack_rec":
                    to_return.append(float(ack_rec))
                elif var == "acks_sent":
                    to_return.append(float(acks_sent))
                elif var == "frames_trans":
                    to_return.append(float(frames_trans))
                elif var == "dup_rec":
                    to_return.append(float(dup_rec))
                elif var == "retrans":
                    to_return.append(float(retrans))
                elif var == "time":
                    t = float(time)
                    if t > 0:
                        to_return.append(t)

    if var != "time":
        new = [to_return[0] + to_return[1],
                to_return[2] + to_return[3],
                to_return[4] + to_return[5],
                to_return[6] + to_return[7],
                to_return[8] + to_return[9]]
        return new


    return to_return

for m in ['GBN', 'SR']:
    for d,c in [('0.00', '0.00'), ('0.05', '0.05'), ('0.20', '0.05'),
                ('0.20', '0.20'), ('0.40', '0.40')]:
        for v in ['ack_rec', 'acks_sent', 'frames_trans', 'dup_rec',
                  'retrans', 'time']:
            print m, d, c, v, (values(d, c, m, v))
            print

