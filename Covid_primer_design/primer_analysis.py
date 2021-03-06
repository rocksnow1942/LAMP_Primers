"""
generate analysis from primer design csv file.
"""
import glob
from ape import REFape,read_primerset_excel,APE
from align_sequence import REF ,BAT
import pandas as pd
from mymodule import revcomp,LazyProperty
import primer3
from itertools import combinations_with_replacement
from collections import Counter,OrderedDict
from primer_para import mv_conc,dv_conc,dntp_conc
from resources import CROSS_GENE_FILE,CROSS_GENE_NAME,CROSS_GENE_NAME_LONG
# from crossreactivity import print_ascii_structure
from Levenshtein import distance
import re
import matplotlib.pyplot as plt
from primer import PrimerDimerfilter,PrimerComplexityfilter,Hairpinfilter
from primer_para import *
from sklearn import preprocessing
import numpy as np
import matplotlib.pyplot as plt

CROSS_GENE_SEQUENCE = [ APE(i).sequence for i in CROSS_GENE_FILE]



def print_ascii_structure(lines,printresult=True):
    if not isinstance(lines,list):
        lines = lines.ascii_structure_lines
    l = lines[0][4:]
    l1 = lines[1][4:]
    start = 4
    end = 4
    ll = len(l)
    for k in range(ll):
        if l[k] != " " or l1[k]!=" ":
            start += k
            break
    for j in range(len(l)):
        if l[ll-j-1]!='-':
            end += ll-j
            break
    if printresult:
        print('\n'.join(i[start:end] for i in lines))
    else:
        return [i[start:end] for i in lines]

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
        r = primer3.bindings.calcHeterodimer(primer[0:60],totest,mv_conc,dv_conc,dntp_conc,)
        tm = r.tm
        if tm>maxtm:
            maxtm = tm
    return maxtm

def draw_hairpin(seq):
    r=primer3.bindings.calcHairpin(seq, mv_conc,dv_conc,dntp_conc,output_structure=True )
    print(r.dg)
    print(r.tm)
    print(r.ascii_structure)

# def HeteroDimerAnneal(primer,sequence):
#     "mv_conc,dv_conc,"
#     length = int(len(sequence)/9000+1)
#     maxtm=-100
#     align = None
#     for i in range(length):
#         totest = sequence[i*9000:(i+1)*9000+100]
#         r = primer3.bindings.calcHeterodimer(primer[0:60],totest,mv_conc,dv_conc,dntp_conc,output_structure=True)
#         tm = r.tm
#         if tm>maxtm:
#             maxtm = tm
#             align = print_ascii_structure(r,printresult=False)
# 
#     return maxtm,align


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
    """
    iterate over primerdesign result from PrimerExplorer website.
    yield: PrimerSetRecord()
    [setname,F3,B3,FIP,BIP,LF,LB,B2c,B1c,F2,F1,gene,B3c,LFc,PEdG]
    """
    keys = ['name','F3','B3','FIP','BIP','LF','LB','B2c','B1c','F2','F1','gene','B3c','LFc', 'PEdG']
    # p1 = re.compile("""<td><span class="dnaString">\[(?P<id>\d*)\]</span></td>(?P<content>.*)<td><span class="dnaString">\[(?P=id)\]</span></td>""",flags=re.DOTALL)
    p1 = re.compile("""<td>\[(?P<id>\d*)\]</td>(?P<content>.*)<td><span class="dnaString">\[(?P=id)\]</span></td>""",flags=re.DOTALL)
    p2 = re.compile('<span class="dnaString" style="color:#(?P<color>.{6});">(?P<seq>[ATCGatcg]*)</span>')
    dG = re.compile('<td align="left">(?P<dG>[-.\d]+)</td>')
    name_counter = Counter()
    for file in files:
        with open(file,'rt') as fr:
            text = fr.read()
        for s in p1.finditer(text):
            content = s['content']
            PEdG = float(dG.search(content)['dG'])
            out = []
            color = ""
            case = None
            for d in p2.finditer(content):
                seq = d['seq']
                if d['color'] != color or case !=seq.isupper():
                    color = d['color']
                    case = seq.isupper()
                    out.append("")
                out[-1]+=seq
            F3,F2,F1c,B1c,B2,B3=[i.upper() for i in out]
            F1c,B2,B3 = F1c[::-1],B2[::-1],B3[::-1]
            B2c = revcomp(B2)
            B3c = revcomp(B3)
            F1 = revcomp(F1c)
            FIP = F1c+F2
            BIP = B1c + B2
            gene = REFape.name_primer(F1)
            name_counter[gene[0]] += 1
            setname = gene[0] + str(name_counter[gene[0]])

            yield PrimerSetRecord(zip(keys,[setname,F3,B3,FIP,BIP,'','',B2c,B1c,F2,F1,gene,B3c,'',PEdG]))

def iter_primerset_lamp_design_csv(*files,skiprows=None,usecols=[1,2],skipfooter=0,return_df=False):
    """
    read all csv files convert to a single DataFrame
    then iterate over primer sets,give it a name based on locus
    yield: PrimerSetRecord()
    [setname,F3,B3,FIP,BIP,LF,LB,B2c,B1c,F2,F1,gene,B3c,LFc,]
    """
    df = pd.DataFrame(columns=['name','seq'])
    dfs = [df]
    for f in files:
        if skiprows == None:
            with open(f,'rt') as ff:
                data = ff.read().split('\n')
            for k,line in enumerate(data):
                if line.startswith('set'):
                    skiprows = k
        _df = pd.read_csv(f,skiprows=list(range(skiprows)),usecols=usecols,skipfooter=skipfooter)
        dfs.append(_df)
    df = pd.concat(dfs,axis=0,ignore_index=True)
    if return_df:
        yield df
    else:
        name_counter = Counter()
        for i in range((len(df)//8)):
            F3, F2, F1, B1c, B2c, B3c, LFc, LB = list(df.loc[i*8:(i*8+7),'seq'])
            names = list(df.loc[i*8:(i*8+7),'name'])
            assert len(set(names)) == 8, f"Primer set incomplete at index {i}."
            gene = REFape.name_primer(F1)
            name_counter[gene[0]] += 1
            setname = gene[0] + str(name_counter[gene[0]])
            yield PrimerSetRecord([setname,F3,revcomp(B3c),revcomp(F1)+F2,
                  B1c+revcomp(B2c),revcomp(LFc),LB,B2c,B1c,F2,F1,gene,B3c,LFc])

def normalizedf(df,columns):
    x = df.loc[:,columns].values
    minmaxscalar = preprocessing.MinMaxScaler()
    x_scaled = minmaxscalar.fit_transform(x)
    df.loc[:,columns] = x_scaled

class PrimerSetRecord(OrderedDict):
    """
    Class to store primer set info.
    data stored in an ordered dict
    [setname,F3,B3,FIP,BIP,LF,LB,B2c,B1c,F2,F1,gene]
    """
    sequence_order = ('F3','B3','FIP','BIP','LF','LB','B2c','B1c','F2','F1')
    fragment_order = ('F3','F2','F1','B3c','B2c','B1c','LFc','LB',)
    primer_order = ('F3','B3','FIP','BIP','LF','LB',)
    corefragment_order = ('F3','F2','F1','B3c','B2c','B1c')
    def __init__(self,inputs):
        if isinstance(inputs,list):
            super().__init__(zip(
            ['name','F3','B3','FIP','BIP','LF','LB','B2c','B1c','F2','F1','gene','B3c','LFc'],inputs))
        else:
            super().__init__(inputs)

    def __hash__(self):
        s = ''.join(i[1] for i in self.iter('corefragment'))
        return s.__hash__()

    @property
    def dg(self):
        return 0
    @property
    def tm(self):
        return 0

    def print(self,contain=''):
        for k,i in self.items():
            if contain in k:
                print(k,'=',i)


    def to_PrimerInfo(self,name=None,inclusivity=0.99,extra=100,extra3=100,toInfo=True):
        if not name:
            if toInfo:
                name = self['name']+ '_PrimerInfo'
            else:
                name = self['name']+ '_PE_Target'
        F3_5pos=REF.find_seq(self['F3'])[1][0]
        F3_3pos=REF.find_seq(self['F3'])[1][1] - F3_5pos + extra
        F2_5pos=REF.find_seq(self['F2'])[1][0] - F3_5pos + extra
        F2_3pos=REF.find_seq(self['F2'])[1][1] - F3_5pos + extra
        F1c_5pos=REF.find_seq(self['F1'])[1][0] - F3_5pos + extra + 2
        F1c_3pos=REF.find_seq(self['F1'])[1][1] - F3_5pos + extra
        B1c_5pos=REF.find_seq(self['B1c'])[1][0] - F3_5pos + extra + 1
        B1c_3pos=REF.find_seq(self['B1c'])[1][1] - F3_5pos + extra
        B2_5pos=REF.find_seq(self['B2c'])[1][0] - F3_5pos + extra + 1
        B2_3pos=REF.find_seq(self['B2c'])[1][1] - F3_5pos + extra
        B3_5pos=REF.find_seq(self['B3c'])[1][0] - F3_5pos + extra + 1
        B3_3pos=REF.find_seq(self['B3c'])[1][1]- F3_5pos + extra
        seq,consensus = REF.to_PE_format(F3_5pos-extra,B3_3pos + extra3-extra + F3_5pos ,inclusivity=inclusivity,save=False)
        with open(name,'wt') as f:
            if toInfo:
                f.write('designID=200429163726\nprimerID=2\n')
                f.write(f'query={seq}\n')
            else:
                f.write(f'sequence={seq}\n')
            f.write(f'consensus={consensus}\n')
            f.write('oligo=0.1\nsodium=50.0\nmagnesium=4.0\ndg_threshold_5=-3\ndg_threshold_3=-4\n')
            f.write("F3_5pos={}\nF3_3pos={}\nF2_5pos={}\nF2_3pos={}\nF1c_5pos={}\nF1c_3pos={}\nB1c_5pos={}\nB1c_3pos={}\nB2_5pos={}\nB2_3pos={}\nB3_5pos={}\nB3_3pos={}\n"
             .format(extra+1,F3_3pos,F2_5pos,F2_3pos,F1c_5pos,F1c_3pos,B1c_5pos,B1c_3pos,B2_5pos,B2_3pos,B3_5pos,B3_3pos))

            if not toInfo:
                f.write('target_range_type=0\ntarget_range_from=\ntarget_range_to=\n')

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

    def to_ape(self,):
        primers = dict(self.iter('primer'))
        return REFape.label_from_primers(primers,name=self['name'])

    @LazyProperty
    def loopF(self):
        return revcomp(REFape[REFape.locate_primer(self['F2'])[0]:REFape.locate_primer(self['F1'])[0]])

    @LazyProperty
    def loopR(self):
        return  REFape[REFape.locate_primer(self['B1c'])[1]:REFape.locate_primer(self['B2c'])[1]]

    # analysis methods start
    def CheckFilter(self):
        pDimerfilter = PrimerDimerfilter(PrimerDimerTm)
        hPfilter = Hairpinfilter(HairpindG)
        LoopHPfilter = Hairpinfilter(LoopHairpindG)
        cmplxfilter = PrimerComplexityfilter()
        result = ""
        dimer =[]
        dimernames=[]
        for n,p in self.iter('primer'):
            if p:
                if not pDimerfilter(p,dimer):
                    result+="!PD="+n+'+'+','.join(dimernames)
                    break
                dimer.append(p)
                dimernames.append(n)

        hPfailed = []
        for n,p in self.iter('primer'):
            if p:
                if not hPfilter(p):
                    hPfailed.append(n)
        if hPfailed: result += '!HP=' + ','.join(hPfailed)

        if not LoopHPfilter(self.loopF[0:60]):
            result += '!LoopF'
        if not LoopHPfilter(self.loopR[0:60]):
            result += '!LoopR'

        cmplxfailed = []
        for n,p in self.iter('fragment'):
            if p:
                if not cmplxfilter(p):
                    cmplxfailed.append(n)
        if cmplxfailed: result += '!CPX='+','.join(cmplxfailed)

        self['checkfilter'] = result
        return self

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

    def Amplicon_len(self):
        if 'A_end' not in self.keys():
            self.Amplicon_pos()
        self['A_length']=self['A_end']-self['A_start']
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
        for (p1,s1),(p2,s2) in combinations_with_replacement(self.iter('primer'),r=2):
            r = primer3.bindings.calcHeterodimer(s1[0:60],s2[0:60],mv_conc,dv_conc,dntp_conc) if s1 and s2 else self
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
        lf = revcomp(REFape[lfs:lfe])[0:60]
        lr = REFape[lrs:lre][0:60]
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
            tm = LongHeteroDimerTm(s,nt) if s else 0
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
        columnname = [f"{i}-CR" for i in CROSS_GENE_NAME_LONG]
        frag = [ j for _,j in self.iter('fragment') if j]
        fragl = len(frag)
        self.update(zip( columnname,
                   (sum( homology_hamming(j,i) for j in frag )/ fragl
                    for i in CROSS_GENE_SEQUENCE)))
        return self

    def Analysis_All(self):
        return (self.Inclusivity()
           .Amplicon_pos()
           .CrossReactivity()
           .Tm()
           .NonTarget()
           .Hairpin()
           .PrimerDimer()
           .LoopHairpin()
           .ExtensionStartGCratio(forward=8)
           .Gaps()
           .GC_ratio()
           .Length()
           .CheckFilter()
            )


class PrimerSetRecordList(list):
    "a list collections of PrimerSetRecord, can be initiated from path to csv."
    def __init__(self,inputs=None,*args,**kwargs):
        if isinstance(inputs,str):
            df = pd.read_csv(inputs,*args,keep_default_na=False,**kwargs)
            super().__init__(df.to_dict(orient="records",into=PrimerSetRecord))
        else:
            super().__init__(inputs or [])

    def __getitem__(self,slice,):
        if isinstance(slice,int):
            return super().__getitem__(slice)
        elif isinstance(slice,str):
            for r in self:
                if r['name']==slice:
                    return r
        elif isinstance(slice,tuple) or isinstance(slice,list):
            return PrimerSetRecordList(i for i in self if i['name'] in slice)
        else:
            return PrimerSetRecordList(super().__getitem__(slice))
    def get(self,name):
        for i in self:
            if i['name'] == name:
                return i
    def __add__(self,b):
        r = list(self) + list(b)
        return PrimerSetRecordList(r)

    def __getattr__(self,attr):
        def wrap(*args,**kwargs):
            [getattr(i,attr)(*args,**kwargs) for i in self]
            return self
        return wrap

    def reindex(self):
        "rename the primers in the set."
        gencounter = Counter()
        for i in self:
            g=i['gene'][0]
            gencounter[g]+=1
            i['name']=f"{g}{gencounter[g]}"
        return self

    @property
    def table(self):
        return pd.DataFrame(self)

    def save_csv(self,path,index=False,**kwargs):
        self.table.to_csv(path,index=index,**kwargs)

    def draw_primerset(self,basepairposition=None,saveas=False,alignwith=None,drawgene=True,drawproperty=[],figwidth=None,figheight=None,drawgrid=False):
        """
        draw ther primers on plot.
        basepairposition: draw only primerset record with A_start and A_end within the interval given.
        saveas: file path to save.
        alignwith: the gene fragment to aligh, defalut align to gene. can be F3, F2, F1, B1c, LFc, LB etc.
        drawgene: choose whether draw the genebar.
        drawproperty: a list of (property_name, property_format) to draw. ('Inclusivity','{:.2%}')
        """
        pl = self
        if basepairposition:
            pl = PrimerSetRecordList(i for i in pl if i['A_start']>=basepairposition[0] and i['A_end']<=basepairposition[1])
        facecolor = ('tab:blue', 'tab:orange', 'tab:green', 'tab:red', 'tab:purple', 'tab:brown', 'tab:pink','tab:olive')

        fig, ax = plt.subplots(figsize=(figwidth or 10,figheight or  0.26*(len(pl)+drawgene)+0.68 ))
        left_pos = [REFape.locate_primer(i['F3'])[0] for i in pl]
        right_pos = [REFape.locate_primer(i['B3c'])[1] for i in pl]
        left_min = min(left_pos)
        right_min = max(right_pos)
        common_fragment = REFape.truncate(left_min,right_min)
        gene_bar = [ (i['start']-1,i['end'] - i['start']+1) for i in common_fragment.features]
        # plot realative position to N gene:
        gene_bar_name = [f"{ i['tag']}:{i['start']+left_min - REFape.get_feature_pos(i['tag'])[0]}-{i['end']+left_min- REFape.get_feature_pos(i['tag'])[0]}" for i in common_fragment.features]
        y_labels = [i['name'] for  i in pl]

        ax.set_yticks(list(range(len(y_labels))))
        if drawgrid:
            ax.grid(axis='y',linewidth=0.3,linestyle='-.')
        ax.set_yticklabels(y_labels)
        ax.set_ylim([-1,len(pl)+drawgene])
        for y,p in enumerate(pl):
            plot_bar = []
            plot_bar_name = []
            for n,i in p.iter('fragment'):
                if i:
                    pos = REFape.locate_primer(i)
                    plot_bar_name.append(n)
                    plot_bar.append((pos[0],pos[1]-pos[0]))
            # if alignwith = F3 or other fragment name, use that position.
            if alignwith:
                _index = plot_bar_name.index(alignwith)
                left_min = plot_bar[_index][0]
            # relative position of the primer to this gene.
            _relative_left = REFape.get_relative_pos(plot_bar[0][0])
            relative_left = f"{_relative_left[1]+1}" if _relative_left else f"{plot_bar[0][0]}"
            _relative_right = REFape.get_relative_pos(plot_bar[3][0])
            relative_right = f"{_relative_right[1]+plot_bar[3][1]}" if _relative_right else f"{plot_bar[3][0]}"

            plot_bar = [(i-left_min,j) for i,j in plot_bar]
            ax.broken_barh(plot_bar, (y - 0.3, 0.6), facecolors=facecolor)
            for n,(_p,w) in zip(plot_bar_name,plot_bar):
                ax.text(_p+w/2,y-0.3,n,ha='center',va='bottom')

            ax.text(plot_bar[0][0]-plot_bar[0][1]*0.05,y-0.3,relative_left,ha='right',va='bottom')
            ax.text(plot_bar[3][0]+plot_bar[3][1]*1.05,y-0.3,relative_right,ha='left',va='bottom')
            if drawproperty:
                propertytext = []
                for i,f in drawproperty:
                    propertytext.append(f.format(p[i]))
                ax.text((right_min - left_min)*1.06, y-0.3 ," "+' | '.join(propertytext), ha='left',va='bottom',family='monospace')

        if drawproperty:
            ax.text((right_min - left_min)*1.06, y+0.7 ,'|'.join(i[0][0:(len(t)+2)] + " "*(len(t)+2 - len(i[0])) for i,t in zip(drawproperty,propertytext)), ha='left',va='bottom',family='monospace')

        # if need to draw gen:
        if drawgene:
            ax.broken_barh(gene_bar,(y+0.7,0.6),facecolor=facecolor)
            for n,(p,w) in zip(gene_bar_name,gene_bar):
                ax.text(p+w/2,y+0.7,n,ha='center',va='bottom')


        ax.set_xticks([])

        plt.tight_layout()

        if saveas:
            plt.savefig(saveas)
        else:
            plt.show()

    def condense(self,sortfunc=None):
        """
        combine similar primer set in the record list, pirmerset with different F2F1B1B2 are considerred different.
        default method is use the B3 F3 primer dimer dG, if similar, use full amplicon length of Astart to Aend.
        """
        collection = {}
        for i in self:
            key = i['F2'] + i['F1']+i['B1c'] + i['B2c']
            if key in collection:
                collection[key].append(i)
            else:
                collection[key]=[i]
        condensed = PrimerSetRecordList()
        def default(r):
            return (-sum(r[i] for i in r.keys() if i.endswith('PDdG') and ('B3' in i or 'F3' in i)) , r['A_end']-r['A_start'],)
        if sortfunc == None:
            sortfunc = default
        for k,i in collection.items():
            condensed.append( sorted(i,key=sortfunc)[0])
        return condensed




if __name__ == '__main__':
    pass
