import os
import glob

class SGFIndex:
    def __init__(self, size=19, url='https://homepages.cwi.nl/~aeb/go/games/games.tgz'):
        self.size = size
        self.url = url
        self.raw_dir = [i for i in self.url[:-4]]
        while '/' in self.raw_dir:
            del self.raw_dir[0]
        self.raw_dir = ''.join(self.raw_dir)
        self.index = []

    def download(self):
        os.system('wget -c %s -O - | tar -xz' %(self.url))

    def create_index(self):
        if self.size!=19:
            for filename in glob.iglob(self.raw_dir+'/'+'**/*.sgf', recursive=True):
                if f"{self.size}x{self.size}" in filename:
                    self.index.append(filename)
        else:   
            nonos = ['other_sizes','unusual','misc','training']
            for filename in glob.iglob(self.raw_dir+'/'+'**/*.sgf', recursive=True):
                if not any(nono in filename for nono in nonos):
                    self.index.append(filename)
