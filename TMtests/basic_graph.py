import csv
import argparse
import numpy as np
from matplotlib import pyplot as plt

def get_groups(filename):
    f = open(filename, 'r')
    reader = csv.reader(f)
    header_row = next(reader)
    groups = []
    for row in reader:
        group = (row[0], row[1], row[4])
        if not group in groups:
            groups.append(group)
    f.close()
    return groups

def get_balance(filename, group):
    f = open(filename, 'r')
    reader = csv.reader(f)
    header_row = next(reader)
    a, b, c = group

    b_wins = 0
    b_margins = 0
    b_range = [9999,0]
    w_margins = 0
    w_range = [9999,0]

    count = 0
    for row in reader:
        if row[0] != a or row[1] != b or row[4] != c:
            continue
        if row[2] == 'Black':
            b_wins += 1
            b_margins += float(row[3])
            if float(row[3]) < b_range[0]:
                b_range[0] = float(row[3])
            if float(row[3]) > b_range[1]:
                b_range[1] = float(row[3])
        else:
            w_margins += float(row[3])
            if float(row[3]) < w_range[0]:
                w_range[0] = float(row[3])
            if float(row[3]) > w_range[1]:
                w_range[1] = float(row[3])
        count += 1
    pct = b_wins/count
    b_margins = b_margins/count
    b_range = b_range[1] - b_range[0]
    w_margins = w_margins/count
    w_range = w_range[1] - w_range[0]
    f.close()
    return [round(pct*100,1), b_margins, b_range, w_margins, w_range]

        
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv-path', type=str, required=True)
    parser.add_argument('--savepath', type=str, required=True)
    args = parser.parse_args()

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate('{}'.format(height),
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), 
                        textcoords="offset points",
                        ha='center', va='bottom')

    if not args.savepath.endswith('.png'):
        args.savepath = args.savepath+'.png'
    filename = args.csv_path
    groups = get_groups(filename)
    balances = []
    for group in groups:
        balance = get_balance(filename, group)
        balances.append(balance) 

    labels = ['black wins\nper 100 games',
              'average\nblack win\nmargin',
              'black win\nmargin\nrange',
              'average\nwhite win\nmargin',
              'white win\nmargin\nrange']
    x = np.arange(len(labels)) 
    width = 0.08
    fig, ax = plt.subplots(figsize=(24,16))

    for i in range(len(groups)):
        offset = width/len(groups)*i*10
        name = 'tm=%s bs=%s k=%s' %(groups[i][0],groups[i][1],groups[i][2])
        rects = ax.bar(x-offset+0.35, balances[i], width, label=name)
        autolabel(rects)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=24)
    plt.tick_params(axis='y', labelsize=24)
    ax.legend(fontsize = 24)
    fig.tight_layout()
    plt.savefig(args.savepath)

if __name__ == '__main__':
    main()
