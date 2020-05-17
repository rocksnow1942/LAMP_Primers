"""
generate analysis from primer design csv file.
"""
import glob
from ape import REFape,read_primerset_excel,APE
from align_sequence import REF #,BAT
import pandas as pd
from mymodule import revcomp,LazyProperty
import primer3
from itertools import product
from collections import Counter,OrderedDict
from primer_para import mv_conc,dv_conc,dntp_conc
from resources import CROSS_GENE_FILE,CROSS_GENE_NAME
from crossreactivity import print_ascii_structure
from Levenshtein import distance

CROSS_GENE_SEQUENCE = [ APE(i).sequence for i in CROSS_GENE_FILE]
CROSS_GENE_SEQUENCE[0][-20:]


def hammingR(s1,s2,):
    return sum(i==j for i,j in zip(s1,s2))


def homology_hamming(s,ref,):
    sr=revcomp(s)
    if (s in ref) or (sr in ref):
        return 1
    d = 0
    sl = len(s)
    rl = len(ref)
    for i in range(rl-sl+1):
        d = max(hammingR(s,ref[i:i+sl]),hammingR(sr,ref[i:i+sl]),d)
    return d/sl


def LongHeteroDimerTm(primer,sequence):
    length = int(len(sequence)/9000+1)
    maxtm=-100
    for i in range(length):
        totest = sequence[i*9000:(i+1)*9000+100]
        r = primer3.bindings.calcHeterodimer(primer,totest,mv_conc,dv_conc,dntp_conc,)
        tm = r.tm
        if tm>maxtm:
            maxtm = tm
    return maxtm


def HeteroDimerAnneal(primer,sequence):
    "mv_conc,dv_conc,"
    length = int(len(sequence)/9000+1)
    maxtm=-100
    align = None
    for i in range(length):
        totest = sequence[i*9000:(i+1)*9000+100]
        r = primer3.bindings.calcHeterodimer(primer,totest,mv_conc,dv_conc,dntp_conc,output_structure=True)
        tm = r.tm
        if tm>maxtm:
            maxtm = tm
            align = print_ascii_structure(r,printresult=False)

    return maxtm,align


def iter_primerset_excel():
    "yield:PrimerSetRecord([setname,F3,B3,FIP,BIP,LF,LB,B2c,B1c,F2,F1,gene,B3c,LFc,])"
    ps = read_primerset_excel()
    for p in ps:
        name = p['set']
        pm = p['feature']
        pd = {i.replace(name+'-',''):j for i,_,j in pm}
        F3 = pd.get('F3',None)
        B3 = pd.get('B3',None)
        F2 = pd.get('F2',None)
        F1c = pd.get('F1c',None)
        B2 = pd.get('B2',None)
        B1c = pd.get('B1c',None)
        LF = pd.get('LF',None)
        LB = pd.get('LB',None)
        gene = REFape.name_primer(revcomp(F1c))
        if all([F3,B3,F2,F1c,B2,B1c,LF,LB]):
            yield PrimerSetRecord([name,F3,B3,F1c+F2,
                  B1c+B2,LF,LB,revcomp(B2),B1c,F2,revcomp(F1c),gene,revcomp(B3),revcomp(LF)])


def iter_primerset_html(files):
    "iterate over primerdesign result from website."




def iter_primerset_lamp_design_csv(files,skiprows=36,usecols=[1,2],skipfooter=0,return_df=False):
    """
    read all csv files convert to a single DataFrame
    then iterate over primer sets,give it a name based on locus
    yield: PrimerSetRecord()
    [setname,F3,B3,FIP,BIP,LF,LB,B2c,B1c,F2,F1,gene,B3c,LFc,]
    """
    df = pd.DataFrame(columns=['name','seq'])
    dfs = [df]
    for f in files:
        _df = pd.read_csv(f,skiprows=list(range(skiprows)),usecols=usecols,skipfooter=skipfooter)
        dfs.append(_df)
    df = pd.concat(dfs,axis=0,ignore_index=True)
    if return_df:
        yield df
    else:
        name_counter = Counter()
        for i in range((len(df)//8)):
            F3, F2, F1, B1c, B2c, B3c, LFc, LB = list(df.loc[i*8:(i*8+7),'seq'])
            gene = REFape.name_primer(F1)
            name_counter[gene[0]] += 1
            setname = gene[0] + str(name_counter[gene[0]])
            yield PrimerSetRecord([setname,F3,revcomp(B3c),revcomp(F1)+F2,
                  B1c+revcomp(B2c),revcomp(LFc),LB,B2c,B1c,F2,F1,gene,B3c,LFc])



class PrimerSetRecord(OrderedDict):
    """
    Class to store primer set info.
    data stored in an ordered dict
    [setname,F3,B3,FIP,BIP,LF,LB,B2c,B1c,F2,F1,gene]
    """
    sequence_order = ('F3','B3','FIP','BIP','LF','LB','B2c','B1c','F2','F1')
    fragment_order = ('F3','F2','F1','B3c','B2c','B1c','LFc','LB',)
    primer_order = ('F3','B3','FIP','BIP','LF','LB',)
    def __init__(self,inputs):
        if isinstance(inputs,list):
            super().__init__(zip(
            ['name','F3','B3','FIP','BIP','LF','LB','B2c','B1c','F2','F1','gene','B3c','LFc'],inputs))
        else:
            super().__init__(inputs)

    @property
    def dg(self):
        return 0
    @property
    def tm(self):
        return 0

    def __str__(self):
        return f"PrimerSetRecord {self['name']} in {self['gene']}"

    def __eq__(self,b):
        return all(i==j for i,j in zip(self.iter('fragment'),b.iter('fragment')))


    def __repr__(self):
        return f"PrimerSetRecord {self['name']} in {self['gene']}"

    def delete(self,*key):
        "same as pop but return itself"
        for i in key:
            self.pop(i)
        return self

    @property
    def table(self):
        "show a table for insepect"
        df=pd.DataFrame.from_dict(self,orient='index',columns=['Value'])
        df.index.name="Key"
        return df

    def iter(self,name):
        r = getattr(self,name+'_order',[])
        for i in r:
            yield i,self[i]
    def iterF(self):
        yield from zip(('F3','F2','F1','B3c','B2c','B1c','LFc','LB'),
        (self['F3'],self['F2'],self['F1'],revcomp(self['B3']),self['B2c'],self['B1c'],revcomp(self['LF']),self['LB']))

    def calc_GC_ratio(self,seq):
        return round((seq.count('G')+seq.count('C'))/len(seq),4) if seq else 0

    @LazyProperty
    def gap_positions(self):
        "return a list of all 12 gap positions, 0 indexed."
        return [j for i in ['F3','F2','F1','B1c','B2c','B3c'] for j in REFape.locate_primer(self[i])]

    def serialize(self):

        return tuple(self.items())

    @classmethod
    def hyrolize(cls,data):
        return cls(data)

    # analysis methods start
    # Order:


    def GC_ratio(self,):
        for p,seq in self.iter('primer'):
            self[p+'-GC%']=self.calc_GC_ratio(seq)
        return self

    def Amplicon_pos(self):
        "locate amplicon; the positions are 0 indexed."
        F3 = self['F3']
        B3c = self['B3c']
        s,_=REFape.locate_primer(F3)
        _,e=REFape.locate_primer(B3c)
        self['A_start']=s
        self['A_end']=e
        return self

    def Length(self,):
        for p,seq in self.iter('primer'):
            r = len(seq)
            self[p+'-Length']=r
        return self

    def Tm(self):
        for p,seq in self.iter('fragment'):
            tm = primer3.bindings.calcTm(seq,mv_conc,dv_conc,dntp_conc,) if seq else 0
            self[p+'-Tm']=round(tm,3)
        return self

    def Hairpin(self):
        for p,seq in self.iter('primer'):
            r=primer3.bindings.calcHairpin(seq, mv_conc,dv_conc,dntp_conc) if seq else self
            self[p+'-HpdG']=round(r.dg/1000,4)
            self[p+'-HpTm']=round(r.tm,3)
        return self

    def PrimerDimer(self):
        for (p1,s1),(p2,s2) in product(self.iter('primer'),repeat=2):
            r = primer3.bindings.calcHeterodimer(s1,s2,mv_conc,dv_conc,dntp_conc) if s1 and s2 else self
            self[p1+'-'+p2+'-PDdG']=round(r.dg/1000,4)
            self[p1+'-'+p2+'-PDTm']=round(r.tm,3)
        return self

    def Inclusivity(self):
        s = list( i[1] for i in self.iter('fragment') if i[1])
        r = REF.check_inclusivity(*s)
        self['Inclusivity']=round(r,5)
        return self


    def Gaps(self):
        "Gap distances between fragments and amplicon length."
        ps = self.gap_positions
        r = [ i-j for i,j in zip(ps[2::2] , ps[1::2])]
        self.update(zip(('Gap1','Gap2','Gap3','Gap4','Gap5'), r ))
        return self

    def LoopHairpin(self):
        "check loop region of amplicon hairpin"
        lfs,_ = REFape.locate_primer(self['F2'])
        lfe,_ = REFape.locate_primer(self['F1'])
        _,lrs = REFape.locate_primer(self['B1c'])
        _,lre = REFape.locate_primer(self['B2c'])
        lf = revcomp(REFape[lfs:lfe])
        lr = REFape[lrs:lre]
        lfr=primer3.bindings.calcHairpin(lf, mv_conc,dv_conc,dntp_conc)
        lrr=primer3.bindings.calcHairpin(lr, mv_conc,dv_conc,dntp_conc)
        self['FloopdG'] = round(lfr.dg/1000,4)
        self['FloopTm'] = round(lfr.tm,3)
        self['RloopdG'] = round(lrr.dg/1000,4)
        self['RloopTm'] = round(lrr.tm,3)
        return self

    def NonTarget(self):
        "Check non target and Tm"
        if ('A_start' not in self) or ('A_end' not in self):
            self.Amplicon_pos()
        s,e = self['A_start'],self['A_end']
        nt = REFape.sequence[0:s] +  REFape.sequence[e:]
        for p,s in self.iter('primer'):
            tm = LongHeteroDimerTm(s,nt)
            self[f'{p}-OTTm'] = round(tm,2)
        return self

    def ExtensionStartGCratio(self,forward=8):
        "the GC ratio at extension start point"
        def f(pos):
            return self.calc_GC_ratio(REFape[pos:pos+forward])
        def r(pos):
            return self.calc_GC_ratio(REFape[pos-forward:pos])

        gs = self.gap_positions
        self.update(zip(
        ('F3extGC%','F2extGC%','F1extGC%','B1extGC%','B2extGC%','B3extGC%'),
        (f(gs[1]),f(gs[3]),f(gs[5]),r(gs[6]),r(gs[8]),r(gs[10]))
        ))
        return self

    def CrossReactivity(self):
        "check cross reactivity with other viruses; using hamming distance"
        columnname = [f"{i}-CR" for i in CROSS_GENE_NAME]
        self.update(zip( columnname,
                   (sum( homology_hamming(j,i) for _,j in self.iter('fragment') )/8
                    for i in CROSS_GENE_SEQUENCE)))
        return self

class PrimerSetRecordList(list):
    "a list collections of PrimerSetRecord, can be initiated from path to csv."
    def __init__(self,inputs,*args,**kwargs):
        if isinstance(inputs,str):
            df = pd.read_csv(inputs,*args,**kwargs)
            super().__init__(df.to_dict(orient="records",into=PrimerSetRecord))
        else:
            super().__init__(inputs)

    def __getitem__(self,slice):
        if isinstance(slice,int):
            return super().__getitem__(slice)
        else:
            return PrimerSetRecordList(super().__getitem__(slice))

    def __getattr__(self,attr):
        def wrap(*args,**kwargs):
            [getattr(i,attr)(*args,**kwargs) for i in self]
            return self
        return wrap

    @property
    def table(self):
        return pd.DataFrame(self)

    def save_csv(self,path,index=False,**kwargs):
        self.table.to_csv(path,index=index,**kwargs)



if __name__ == '__main__':
    pl = PrimerSetRecordList('./LAMP_primer_design_output/my_lamp_primers.csv')
