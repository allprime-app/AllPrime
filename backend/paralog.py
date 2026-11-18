# -*- coding: utf-8 -*-
# AllPrime - Primer Tasarim Araci
# Copyright (c) 2026 AllPrime eser sahibi - bkz. AUTHORS
#
# GNU GPL surum 2 ya da (isteginize gore) daha sonraki bir surumu ile lisanslidir
# (GPL-2.0-or-later); tam metin LICENSE dosyasinda. Lisans degistirme hakki
# verir, ancak telif bildiriminin korunmasini sart kosar (GPL v2 md. 1 ve 2/a).
"""
AllPrime - Yakin-ozdes paralog / psodogen uyarisi

Bazi genlerin genomda neredeyse birebir ikizi vardir: PMS2/PMS2CL,
CYP21A2/CYP21A1P, NCF1/NCF1B-NCF1C, HBA1/HBA2, SMN1/SMN2, STRC/STRCP1... Bu genlerde
tasarlanan primer kopyadan da urun verebilir; iki lokus birlikte cogalinca
hastanin varyanti seyrelir ya da kopyaninki hastaya yazilir. Tasarim bunu
KENDILIGINDEN kontrol etmez (ozgulluk taramasi kullanicinin istegine bagli,
dugmeyle calisir) - bu yuzden boyle bir gende calisirken ONCEDEN haber verilir.

Uyari bir hukum degil, hatirlatmadir: hangi ciftin gercekten kopyadan da urun
verdigini yalnizca "Ozgullugu kontrol et" soyler.

TABLO NASIL URETILDI  (scratchpad/paralog_uret2.py, 2026-10-25, yerel GRCh37 FASTA)
  1. Aday ciftler gen sembolu ailesinden cikarildi (sondaki P1/CL/B/rakam
     atilarak ayni koke inen semboller: PMS2-PMS2CL, SMN1-SMN2, HBA1-HBA2,
     CYP21A2-CYP21A1P, C4A-C4B, OPN1LW-OPN1MW...).
  2. Her aday GERCEK DIZIYLE olculdu: genden 500 bp'lik pencereler alinir,
     pencerenin ortasindaki 20-mer (primer boyu) paralog bolgesinde aranir,
     bulundugu yerden 500 bp boyunca kimlik hesaplanir; >=%90 ise o pencere
     "homolog" sayilir. Iki yon de taranir.
  3. 500 bp sarti BILEREK konuldu. Ilk denemede tek tek 20-mer sayilmisti ve o
     olcum BRCA1 ile BRCA2'ye bile %7,8 veriyordu - tamami intronlardaki Alu
     tekrarlarindan geliyordu. Alu ~300 bp oldugu icin 500 bp'yi %90 kimlikle
     tasiyamaz; gercek paralog tasir.
  4. 'dna'  = gen govdesi (intronlar dahil) pencerelerinin yuzdesi -> genomik
     tasarim riski.
     'ekzon' = yalnizca ekzon pencerelerinin yuzdesi -> cDNA / RNA riski.
     Islenmis (intronsuz) psodogende ekzon yuksek, dna dusuk cikar; uyari bunu
     ayirir, cunku o durumda yalnizca ekzon uzerindeki primerler etkilenir.
  5. Tabloya iki olcumden biri >=%10 olan ciftler alindi (813 genden 712'si).
     Tablodaki kopyalarin COGU psodogen degil, AYRI BIR GEN: gen aileleri
     (ADH1A/B/C, BTN3A1/2/3, MYH6/MYH7). Metin bunu 'paralog gen' / 'psodogen'
     diye ayirir (refGene'de NM_ kaydi varsa gen). Bu ailelerde govde benzerligi
     dusuk, benzerlik ekzonlarda yogundur; uyari da o zaman yalnizca ekzon
     uzerindeki primerleri isaret eder.

Olcum GRCh37'de yapildi; paraloglugun kendisi genom surumune bagli degildir,
tablo iki surumde de kullanilir. Kromozom adi bilgi icindir.
"""

from lang import t

ESIK = 10.0          # tabloya giris esigi: max(dna, ekzon) >= bu (yuzde)
KIMLIK_ESIGI = 90    # pencere "homolog" sayilmasi icin gereken kimlik (yuzde)
PENCERE = 500        # olcum penceresi (bp)
# Uyarinin CIKMA esikleri moda gore ayri. Genomik tasarimda asil olcu gen govdesi;
# govde benzerligi dusuk ama benzerlik ekzonlarda yogunsa (gen aileleri: ADH1A/B/C,
# MYH6/MYH7) yalnizca ekzon uzerine oturan primer etkilenir - bu daha yuksek bir
# esikte, ayri bir cumleyle soylenir. Yoksa zayif aile benzerlikleri gurultu yapardi.
DNA_ESIK = 10.0
CDNA_ESIK = 10.0
EKZON_YOGUN_ESIK = 20.0

# gen -> [(paralog adi, kromozom, dna %, ekzon %, paralog kodlayan mi)]
PARALOGLAR = {
    "ABCC6": (("ABCC6P1", "16", 15.8, 11.7, False),),
    "ACOT1": (("ACOT2", "14", 10.0, 34.2, True),),
    "ACOT2": (("ACOT1", "14", 7.5, 44.2, True),),
    "ACSM2A": (("ACSM2B", "16", 43.3, 47.5, True),),
    "ACSM2B": (("ACSM2A", "16", 33.3, 55.0, True),),
    "ACTR3C": (("ACTR3B", "7", 10.0, 0, True),),
    "ADH1A": (("ADH1B", "4", 0, 35.0, True), ("ADH1C", "4", 0.8, 25.0, True),),
    "ADH1B": (("ADH1C", "4", 0.8, 11.7, True),),
    "ADH1C": (("ADH1B", "4", 0.8, 45.8, True), ("ADH1A", "4", 0, 25.0, True),),
    "AGAP11": (("AGAP5", "10", 10.8, 21.7, True), ("AGAP4", "10", 9.2, 21.7, True), ("AGAP6", "10", 12.5, 16.7, True),),
    "AGAP4": (("AGAP5", "10", 33.3, 62.5, True), ("AGAP6", "10", 38.3, 57.5, True), ("AGAP9", "10", 32.5, 40.8, True),),
    "AGAP5": (("AGAP9", "10", 41.7, 23.3, True), ("AGAP4", "10", 38.3, 23.3, True), ("AGAP6", "10", 34.2, 21.7, True),),
    "AGAP6": (("AGAP4", "10", 45.0, 45.0, True), ("AGAP5", "10", 38.3, 43.3, True), ("AGAP9", "10", 40.0, 31.7, True),),
    "AGAP9": (("AGAP5", "10", 50.0, 65.8, True), ("AGAP4", "10", 35.8, 51.7, True), ("AGAP6", "10", 37.5, 47.5, True),),
    "AHCTF1": (("AHCTF1P1", "2", 0.8, 54.2, False),),
    "AKR1B10": (("AKR1B15", "7", 9.2, 33.3, True),),
    "AKR1B15": (("AKR1B10", "7", 5.0, 35.8, True),),
    "AKR1C1": (("AKR1C2", "10", 26.7, 18.3, True),),
    "AKR1C2": (("AKR1C1", "10", 13.3, 36.7, True),),
    "AKR1C3": (("AKR1C1", "10", 0, 27.5, True), ("AKR1C2", "10", 0, 25.8, True),),
    "AKR7A2": (("AKR7A3", "1", 0, 16.7, True),),
    "AKR7A3": (("AKR7A2", "1", 0.8, 24.2, True), ("AKR7A2P1", "1", 0, 17.5, False),),
    "ALG10": (("ALG10B", "12", 19.2, 1.7, True),),
    "ALG10B": (("ALG10", "12", 10.8, 0.8, True),),
    "AMY1A": (("AMY2A", "1", 7.5, 57.5, True), ("AMY2B", "1", 0.8, 55.8, True),),
    "AMY1B": (("AMY2A", "1", 9.2, 55.8, True), ("AMY2B", "1", 0.8, 53.3, True),),
    "AMY1C": (("AMY2A", "1", 6.7, 59.2, True), ("AMY2B", "1", 0.8, 55.8, True),),
    "AMY2A": (("AMY2B", "1", 3.3, 75.8, True), ("AMY1A", "1", 44.2, 66.7, True), ("AMY1C", "1", 44.2, 66.7, True),),
    "AMY2B": (("AMY2A", "1", 3.3, 49.2, True), ("AMY1A", "1", 1.7, 42.5, True), ("AMY1C", "1", 1.7, 42.5, True),),
    "ANAPC1": (("ANAPC1P4", "2", 6.7, 13.3, False), ("ANAPC1P2", "2", 7.5, 10.0, False),),
    "ANKRD20A1": (("ANKRD20A8P", "2", 37.5, 32.5, False), ("ANKRD20A5P", "18", 5.8, 10.8, False),),
    "ANP32D": (("ANP32A", "15", 0, 15.0, True),),
    "ANXA2": (("ANXA2P2", "9", 0, 51.7, False),),
    "AOC3": (("AOC4P", "17", 10.0, 16.7, False),),
    "APOBEC3A": (("APOBEC3B", "22", 28.3, 23.3, True),),
    "APOBEC3B": (("APOBEC3A", "22", 14.2, 15.0, True),),
    "APOBEC3D": (("APOBEC3F", "22", 6.7, 19.2, True),),
    "AQP12A": (("AQP12B", "2", 87.5, 73.3, True),),
    "AQP12B": (("AQP12A", "2", 91.7, 89.2, True),),
    "AQP7": (("AQP7P1", "9", 28.3, 8.3, False), ("AQP7P3", "9", 28.3, 0, False),),
    "ASAH2": (("ASAH2B", "10", 15.8, 43.3, True),),
    "ASAH2B": (("ASAH2", "10", 62.5, 45.0, True),),
    "ASB9": (("ASB9P1", "15", 0, 10.8, False),),
    "ATAD3A": (("ATAD3B", "1", 20.8, 51.7, True), ("ATAD3C", "1", 6.7, 12.5, True),),
    "ATAD3B": (("ATAD3A", "1", 14.2, 31.7, True),),
    "BMP8A": (("BMP8B", "1", 30.8, 14.2, True),),
    "BMP8B": (("BMP8A", "1", 36.7, 15.8, True),),
    "BOLA2": (("BOLA2B", "16", 100.0, 0, True),),
    "BOLA2B": (("BOLA2", "16", 100.0, 0, True),),
    "BPY2": (("BPY2B", "Y", 100.0, 99.2, True), ("BPY2C", "Y", 100.0, 99.2, True),),
    "BPY2B": (("BPY2", "Y", 100.0, 99.2, True), ("BPY2C", "Y", 100.0, 99.2, True),),
    "BPY2C": (("BPY2", "Y", 100.0, 99.2, True), ("BPY2B", "Y", 100.0, 99.2, True),),
    "BTN2A1": (("BTN2A2", "6", 0.8, 12.5, True),),
    "BTN3A1": (("BTN3A2", "6", 2.5, 11.7, True), ("BTN3A3", "6", 1.7, 10.8, True),),
    "BTN3A2": (("BTN3A3", "6", 10.8, 10.0, True),),
    "BTN3A3": (("BTN3A2", "6", 10.8, 15.8, True), ("BTN3A1", "6", 0.8, 10.8, True),),
    "C1QTNF9B": (("C1QTNF9", "13", 20.0, 0, True),),
    "C2CD4B": (("C2CD4A", "15", 10.0, 11.7, True),),
    "CATSPER2": (("CATSPER2P1", "15", 10.8, 0, False),),
    "CBWD1": (("CBWD3", "9", 46.7, 64.2, True), ("CBWD2", "2", 54.2, 61.7, True), ("CBWD6", "9", 45.0, 56.7, True),),
    "CBWD2": (("CBWD1", "9", 58.3, 55.8, True), ("CBWD5", "9", 51.7, 28.3, True), ("CBWD3", "9", 50.0, 36.7, True),),
    "CBWD3": (("CBWD6", "9", 69.2, 90.8, True), ("CBWD1", "9", 42.5, 71.7, True), ("CBWD5", "9", 51.7, 47.5, True),),
    "CBWD5": (("CBWD3", "9", 60.8, 18.3, True), ("CBWD2", "2", 45.8, 17.5, True), ("CBWD6", "9", 45.0, 24.2, True),),
    "CBWD6": (("CBWD3", "9", 70.8, 91.7, True), ("CBWD1", "9", 39.2, 61.7, True), ("CBWD5", "9", 45.8, 49.2, True),),
    "CCZ1": (("CCZ1B", "7", 56.7, 81.7, True),),
    "CCZ1B": (("CCZ1", "7", 50.0, 96.7, True),),
    "CD8B": (("CD8B2", "2", 30.0, 19.2, True),),
    "CD8B2": (("CD8B", "2", 25.0, 4.2, True),),
    "CDRT15": (("CDRT15P1", "17", 75.0, 0, False),),
    "CDY1": (("CDY1B", "Y", 100.0, 100.0, True), ("CDY2A", "Y", 51.7, 61.7, True), ("CDY2B", "Y", 51.7, 60.8, True),),
    "CDY1B": (("CDY1", "Y", 100.0, 100.0, True), ("CDY2A", "Y", 51.7, 61.7, True), ("CDY2B", "Y", 51.7, 60.8, True),),
    "CDY2A": (("CDY1", "Y", 1.7, 64.2, True), ("CDY1B", "Y", 1.7, 64.2, True),),
    "CDY2B": (("CDY1", "Y", 2.5, 65.0, True), ("CDY1B", "Y", 2.5, 65.0, True),),
    "CEACAM3": (("CEACAM1", "19", 0, 15.0, True), ("CEACAM6", "19", 0, 12.5, True),),
    "CEACAM6": (("CEACAM1", "19", 0, 10.0, True),),
    "CEL": (("CELP", "9", 20.8, 7.5, False),),
    "CELA2A": (("CELA2B", "1", 1.7, 50.0, True),),
    "CELA2B": (("CELA2A", "1", 0, 50.0, True),),
    "CELA3A": (("CELA3B", "1", 20.8, 40.0, True),),
    "CELA3B": (("CELA3A", "1", 19.2, 40.0, True),),
    "CENPVL1": (("CENPVL3", "X", 5.0, 65.0, True),),
    "CENPVL2": (("CENPVL3", "X", 5.0, 65.0, True),),
    "CENPVL3": (("CENPVL1", "X", 55.8, 55.8, True), ("CENPVL2", "X", 55.8, 55.8, True),),
    "CES1": (("CES1P1", "16", 10.0, 15.8, False), ("CES1P2", "16", 1.7, 10.8, False),),
    "CFC1": (("CFC1B", "2", 86.7, 96.7, True),),
    "CFC1B": (("CFC1", "2", 87.5, 97.5, True),),
    "CFHR1": (("CFHR2", "1", 17.5, 9.2, True),),
    "CFHR2": (("CFHR1", "1", 13.3, 6.7, True),),
    "CFHR3": (("CFHR4", "1", 10.8, 1.7, True),),
    "CGB1": (("CGB2", "19", 70.8, 15.8, True), ("CGB8", "19", 70.8, 20.0, True), ("CGB5", "19", 69.2, 19.2, True),),
    "CGB2": (("CGB1", "19", 70.8, 9.2, True), ("CGB8", "19", 69.2, 12.5, True), ("CGB3", "19", 65.8, 12.5, True),),
    "CGB3": (("CGB5", "19", 55.0, 92.5, True), ("CGB8", "19", 56.7, 77.5, True), ("CGB7", "19", 45.8, 68.3, True),),
    "CGB5": (("CGB3", "19", 54.2, 92.5, True), ("CGB8", "19", 80.8, 83.3, True), ("CGB7", "19", 63.3, 71.7, True),),
    "CGB7": (("CGB5", "19", 26.7, 21.7, True), ("CGB3", "19", 16.7, 24.2, True), ("CGB8", "19", 23.3, 21.7, True),),
    "CGB8": (("CGB5", "19", 80.8, 83.3, True), ("CGB3", "19", 56.7, 77.5, True), ("CGB7", "19", 63.3, 69.2, True),),
    "CKMT1A": (("CKMT1B", "15", 77.5, 71.7, True),),
    "CKMT1B": (("CKMT1A", "15", 75.8, 42.5, True),),
    "CLCNKA": (("CLCNKB", "1", 6.7, 40.0, True),),
    "CLCNKB": (("CLCNKA", "1", 4.2, 43.3, True),),
    "CLK2": (("CLK2P1", "7", 0, 21.7, False),),
    "CR1": (("CR1L", "1", 1.7, 13.3, True),),
    "CR1L": (("CR1", "1", 0, 28.3, True),),
    "CSAG1": (("CSAG4", "X", 13.3, 0, False),),
    "CSH1": (("CSH2", "17", 75.0, 91.7, True),),
    "CSH2": (("CSH1", "17", 68.3, 89.2, True),),
    "CSNK2A1": (("CSNK2A3", "11", 0, 34.2, True),),
    "CSNK2A3": (("CSNK2A1", "20", 0, 88.3, True),),
    "CST1": (("CST4", "20", 11.7, 55.8, True), ("CST2", "20", 10.8, 0, True),),
    "CST4": (("CST1", "20", 11.7, 55.8, True),),
    "CT45A1": (("CT45A10", "X", 67.5, 25.8, True),),
    "CT45A10": (("CT45A1", "X", 67.5, 41.7, True), ("CT45A6", "X", 67.5, 54.2, True), ("CT45A2", "X", 45.8, 54.2, True),),
    "CT45A2": (("CT45A10", "X", 80.8, 55.8, True), ("CT45A3", "X", 65.8, 65.8, True),),
    "CT45A3": (("CT45A2", "X", 64.2, 84.2, True), ("CT45A8", "X", 64.2, 84.2, True), ("CT45A9", "X", 64.2, 84.2, True),),
    "CT45A5": (("CT45A10", "X", 80.8, 52.5, True), ("CT45A3", "X", 65.8, 63.3, True),),
    "CT45A6": (("CT45A10", "X", 80.0, 25.8, True),),
    "CT45A8": (("CT45A10", "X", 81.7, 34.2, True), ("CT45A3", "X", 60.8, 55.8, True),),
    "CT45A9": (("CT45A10", "X", 80.8, 49.2, True), ("CT45A3", "X", 65.8, 67.5, True),),
    "CT47A1": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A10": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A11": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A12": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A2": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A3": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A4": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A5": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A6": (("CT47B1", "X", 30.8, 6.7, True),),
    "CT47A7": (("CT47B1", "X", 31.7, 6.7, True),),
    "CT47A8": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47A9": (("CT47B1", "X", 28.1, 6.7, True),),
    "CT47B1": (("CT47A1", "X", 32.5, 1.7, True), ("CT47A10", "X", 32.5, 1.7, True), ("CT47A11", "X", 32.5, 1.7, True),),
    "CTAG1B": (("CTAG2", "X", 0.8, 15.0, True),),
    "CTAG2": (("CTAG1A", "X", 0.8, 10.0, True), ("CTAG1B", "X", 0.8, 10.0, True),),
    "CTAGE1": (("CTAGE10P", "13", 11.7, 11.7, False),),
    "CTAGE15": (("CTAGE6", "7", 95.8, 95.8, True), ("CTAGE4", "7", 78.3, 75.0, True), ("CTAGE8", "7", 78.3, 75.0, True),),
    "CTAGE4": (("CTAGE9", "6", 5.0, 88.3, True), ("CTAGE15", "7", 2.5, 75.0, True), ("CTAGE6", "7", 2.5, 73.3, True),),
    "CTAGE6": (("CTAGE15", "7", 95.0, 95.0, True), ("CTAGE4", "7", 71.7, 69.2, True), ("CTAGE8", "7", 71.7, 69.2, True),),
    "CTAGE8": (("CTAGE9", "6", 7.5, 71.7, True), ("CTAGE15", "7", 5.0, 60.0, True), ("CTAGE6", "7", 4.2, 59.2, True),),
    "CTAGE9": (("CTAGE4", "7", 92.5, 91.7, True), ("CTAGE8", "7", 92.5, 91.7, True), ("CTAGE15", "7", 67.5, 67.5, True),),
    "CTRB1": (("CTRB2", "16", 21.7, 100.0, True),),
    "CTRB2": (("CTRB1", "16", 45.8, 100.0, True),),
    "CXADR": (("CXADRP2", "15", 0, 10.0, False),),
    "CYP11B1": (("CYP11B2", "8", 18.3, 17.5, True),),
    "CYP11B2": (("CYP11B1", "8", 20.0, 26.7, True),),
    "CYP21A2": (("CYP21A1P", "6", 52.5, 47.5, False),),
    "CYP2A13": (("CYP2A6", "19", 6.7, 42.5, True), ("CYP2A7", "19", 5.8, 36.7, True),),
    "CYP2A6": (("CYP2A7", "19", 35.0, 50.0, True), ("CYP2A13", "19", 9.2, 40.0, True),),
    "CYP2A7": (("CYP2A6", "19", 28.3, 40.8, True), ("CYP2A13", "19", 9.2, 30.0, True),),
    "CYP2B6": (("CYP2B7P", "19", 4.2, 25.8, False),),
    "CYP2C19": (("CYP2C9", "10", 0, 10.8, True),),
    "CYP2C9": (("CYP2C19", "10", 5.8, 19.2, True),),
    "CYP2D6": (("CYP2D7", "22", 26.7, 43.3, True),),
    "CYP2D7": (("CYP2D6", "22", 24.2, 24.2, True),),
    "CYP3A4": (("CYP3A7", "7", 1.7, 20.0, True),),
    "CYP3A7": (("CYP3A4", "7", 0.8, 28.3, True),),
    "CYP4A11": (("CYP4A22", "1", 35.8, 46.7, True),),
    "CYP4A22": (("CYP4A11", "1", 38.3, 48.3, True),),
    "CYP4F2": (("CYP4F3", "19", 3.3, 55.0, True),),
    "CYP4F3": (("CYP4F2", "19", 4.2, 22.5, True),),
    "CYP4Z1": (("CYP4Z2P", "1", 37.5, 43.3, False),),
    "DAZ1": (("DAZ3", "Y", 84.2, 73.3, True), ("DAZ4", "Y", 84.2, 83.3, True), ("DAZ2", "Y", 80.8, 75.8, True),),
    "DAZ2": (("DAZ4", "Y", 85.0, 80.0, True), ("DAZ3", "Y", 75.0, 84.2, True), ("DAZ1", "Y", 82.5, 80.0, True),),
    "DAZ3": (("DAZ2", "Y", 82.5, 89.2, True), ("DAZ1", "Y", 83.3, 82.5, True), ("DAZ4", "Y", 83.3, 80.8, True),),
    "DAZ4": (("DAZ2", "Y", 70.8, 82.5, True), ("DAZ3", "Y", 81.7, 76.7, True), ("DAZ1", "Y", 68.3, 80.8, True),),
    "DCAF13": (("DCAF13P3", "15", 0, 10.0, False),),
    "DEFA1": (("DEFA3", "8", 20.0, 0, True),),
    "DEFA1B": (("DEFA3", "8", 20.0, 0, True),),
    "DEFA3": (("DEFA1", "8", 70.0, 0, True), ("DEFA1B", "8", 70.0, 0, True),),
    "DENND10": (("DENND10P1", "X", 1.7, 65.0, False),),
    "DGCR6": (("DGCR6L", "22", 3.3, 68.3, True),),
    "DGCR6L": (("DGCR6", "22", 5.0, 61.7, True),),
    "DHRS4L1": (("DHRS4L2", "14", 15.0, 12.5, True),),
    "DHRS4L2": (("DHRS4L1", "14", 21.7, 5.8, True),),
    "DPRX": (("DPRXP4", "17", 0, 39.2, False),),
    "DPY19L2": (("DPY19L2P1", "7", 26.7, 25.8, False), ("DPY19L2P2", "7", 26.7, 16.7, False),),
    "DRD5": (("DRD5P2", "1", 14.2, 17.5, False),),
    "DUOX1": (("DUOX2", "15", 0.8, 15.0, True),),
    "EIF2S3": (("EIF2S3B", "12", 0, 21.7, True),),
    "EIF2S3B": (("EIF2S3", "X", 0, 45.0, True),),
    "EMB": (("EMBP1", "1", 10.8, 14.2, False),),
    "EOLA1": (("EOLA2", "X", 25.8, 3.3, True),),
    "EOLA2": (("EOLA1", "X", 53.3, 17.5, True),),
    "ERVV-1": (("ERVV-2", "19", 44.2, 44.2, True),),
    "ERVV-2": (("ERVV-1", "19", 16.7, 34.2, True),),
    "ESPN": (("ESPNP", "1", 8.3, 11.7, False),),
    "F8A1": (("F8A2", "X", 95.8, 70.0, True), ("F8A3", "X", 5.0, 95.8, True),),
    "F8A2": (("F8A1", "X", 4.2, 99.2, True), ("F8A3", "X", 4.2, 99.2, True),),
    "F8A3": (("F8A1", "X", 97.5, 96.7, True), ("F8A2", "X", 97.5, 70.8, True),),
    "FAHD2A": (("FAHD2B", "2", 14.2, 11.7, True), ("FAHD2CP", "2", 14.2, 0, False),),
    "FAHD2B": (("FAHD2A", "2", 15.8, 49.2, True), ("FAHD2CP", "2", 30.8, 0, False),),
    "FAM86B1": (("FAM86B2", "8", 80.8, 33.3, True), ("FAM86B3P", "8", 23.3, 0, False),),
    "FAM86B2": (("FAM86B1", "8", 83.3, 69.2, True), ("FAM86B3P", "8", 27.5, 0.8, False), ("FAM86C2P", "11", 10.8, 0, False),),
    "FAM90A1": (("FAM90A7P", "8", 26.7, 40.0, False), ("FAM90A2P", "8", 35.8, 12.5, False), ("FAM90A26", "4", 27.5, 34.2, True),),
    "FAM90A26": (("FAM90A1", "12", 36.7, 50.0, True), ("FAM90A7P", "8", 38.3, 48.3, False), ("FAM90A2P", "8", 43.3, 23.3, False),),
    "FCGR1A": (("FCGR1B", "1", 35.8, 25.0, False), ("FCGR1CP", "1", 34.2, 30.8, False),),
    "FCGR2A": (("FCGR2C", "1", 28.3, 17.5, True),),
    "FCGR2B": (("FCGR2C", "1", 66.7, 16.7, True),),
    "FCGR2C": (("FCGR2B", "1", 55.0, 13.3, True), ("FCGR2A", "1", 19.2, 14.2, True),),
    "FCGR3A": (("FCGR3B", "1", 27.5, 30.8, True),),
    "FCGR3B": (("FCGR3A", "1", 31.7, 33.3, True),),
    "FDPS": (("FDPSP2", "7", 0, 11.7, False),),
    "FOLH1": (("FOLH1B", "11", 21.7, 28.3, True),),
    "FOLH1B": (("FOLH1", "11", 25.8, 67.5, True),),
    "FOXD4L1": (("FOXD4L3", "9", 28.3, 28.3, True), ("FOXD4L6", "9", 24.2, 24.2, True), ("FOXD4L4", "9", 12.5, 12.5, True),),
    "FOXD4L3": (("FOXD4L6", "9", 95.8, 94.2, True), ("FOXD4L4", "9", 41.7, 36.7, True), ("FOXD4L5", "9", 41.7, 41.7, True),),
    "FOXD4L4": (("FOXD4L5", "9", 88.3, 88.3, True), ("FOXD4L6", "9", 86.7, 86.7, True), ("FOXD4L3", "9", 82.5, 82.5, True),),
    "FOXD4L5": (("FOXD4L4", "9", 90.0, 34.2, True), ("FOXD4L3", "9", 35.8, 34.2, True), ("FOXD4L6", "9", 35.8, 33.3, True),),
    "FOXD4L6": (("FOXD4L3", "9", 95.8, 95.8, True), ("FOXD4L4", "9", 44.2, 44.2, True), ("FOXD4L5", "9", 44.2, 44.2, True),),
    "FOXL2": (("FOXL2NB", "3", 16.7, 0, True),),
    "FOXL2NB": (("FOXL2", "3", 10.8, 0, True),),
    "FOXO3": (("FOXO3B", "17", 3.3, 47.5, True),),
    "FOXO3B": (("FOXO3", "6", 16.7, 57.5, True),),
    "FRG2": (("FRG2B", "10", 60.8, 37.5, True), ("FRG2C", "3", 19.2, 19.2, True), ("FRG2EP", "3", 19.2, 19.2, False),),
    "FRG2B": (("FRG2", "4", 62.5, 38.3, True), ("FRG2C", "3", 17.5, 18.3, True), ("FRG2EP", "3", 17.5, 18.3, False),),
    "FRG2C": (("FRG2", "4", 15.0, 18.3, True), ("FRG2B", "10", 16.7, 14.2, True),),
    "FRMD8": (("FRMD8P1", "X", 0, 15.0, False),),
    "FRMPD2": (("FRMPD2B", "10", 13.3, 29.2, False),),
    "FUT3": (("FUT5", "19", 3.3, 20.0, True), ("FUT6", "19", 2.5, 12.5, True),),
    "FUT5": (("FUT3", "19", 9.2, 29.2, True), ("FUT6", "19", 6.7, 20.0, True),),
    "FUT6": (("FUT5", "19", 5.0, 14.2, True), ("FUT3", "19", 3.3, 12.5, True),),
    "GBA": (("GBAP1", "1", 19.2, 25.0, False),),
    "GBP1": (("GBP3", "1", 0, 10.8, True),),
    "GBP3": (("GBP1", "1", 0, 10.0, True),),
    "GGT1": (("GGT2", "22", 17.5, 30.0, True), ("GGT3P", "22", 14.2, 21.7, False), ("GGTLC1", "20", 2.5, 11.7, True),),
    "GGT2": (("GGT1", "22", 12.5, 30.0, True), ("GGT3P", "22", 17.5, 22.5, False), ("GGTLC3", "22", 2.5, 19.2, True),),
    "GGTLC1": (("GGT1", "22", 39.2, 64.2, True), ("GGTLC3", "22", 23.3, 45.0, True), ("GGTLC2", "22", 43.3, 0, True),),
    "GGTLC2": (("GGT1", "22", 50.8, 0, True), ("GGTLC1", "20", 46.7, 0, True), ("GGT2", "22", 35.8, 0, True),),
    "GGTLC3": (("GGT2", "22", 94.2, 91.7, True), ("GGT3P", "22", 65.8, 34.2, False), ("GGT1", "22", 44.2, 54.2, True),),
    "GLUD1": (("GLUD2", "X", 0, 25.8, True),),
    "GLUD2": (("GLUD1", "10", 3.3, 35.0, True),),
    "GLYATL1B": (("GLYATL1", "11", 2.5, 16.7, True),),
    "GMCL1": (("GMCL2", "5", 0, 15.0, True),),
    "GMCL2": (("GMCL1", "2", 0, 21.7, True),),
    "GOLGA6L1": (("GOLGA6L22", "15", 76.7, 70.0, True), ("GOLGA6L6", "15", 69.2, 58.3, True),),
    "GOLGA6L10": (("GOLGA6L4", "15", 6.7, 62.5, True), ("GOLGA6L5P", "15", 8.6, 60.0, False), ("GOLGA6L3", "15", 3.8, 10.0, True),),
    "GOLGA6L22": (("GOLGA6L1", "15", 10.6, 67.5, True), ("GOLGA6L6", "15", 65.0, 58.3, True),),
    "GOLGA6L3": (("GOLGA6L4", "15", 52.5, 35.0, True), ("GOLGA6L5P", "15", 52.5, 36.7, False),),
    "GOLGA6L4": (("GOLGA6L5P", "15", 79.2, 57.5, False), ("GOLGA6L3", "15", 41.7, 15.0, True),),
    "GOLGA6L6": (("GOLGA6L22", "15", 74.2, 51.7, True), ("GOLGA6L1", "15", 68.3, 53.3, True),),
    "GOLGA6L9": (("GOLGA6L4", "15", 8.7, 36.7, True), ("GOLGA6L5P", "15", 8.7, 35.8, False), ("GOLGA6L3", "15", 2.9, 13.3, True),),
    "GRAP": (("GRAPL", "17", 75.0, 0, True),),
    "GRAPL": (("GRAP", "17", 62.5, 0, True),),
    "GSTA1": (("GSTA2", "6", 9.2, 40.0, True), ("GSTA3", "6", 0, 10.8, True),),
    "GSTA2": (("GSTA1", "6", 9.2, 43.3, True),),
    "GSTA3": (("GSTA1", "6", 0, 26.7, True), ("GSTA2", "6", 0, 19.2, True),),
    "GSTA5": (("GSTA1", "6", 1.7, 22.5, True), ("GSTA2", "6", 0.8, 17.5, True),),
    "GSTM1": (("GSTM4", "1", 10.0, 26.7, True), ("GSTM2", "1", 19.2, 0, True), ("GSTM5", "1", 1.7, 15.0, True),),
    "GSTM2": (("GSTM1", "1", 11.7, 0, True),),
    "GSTM4": (("GSTM1", "1", 5.0, 20.8, True),),
    "GTF2H2": (("GTF2H2C", "5", 71.7, 93.3, True), ("GTF2H2B", "5", 75.0, 37.5, False),),
    "GTF2H2C": (("GTF2H2", "5", 74.2, 25.8, True), ("GTF2H2B", "5", 73.3, 65.8, False),),
    "GTF2I": (("GTF2IP4", "7", 23.3, 67.5, False), ("GTF2IP1", "7", 22.5, 67.5, False),),
    "GTF2IRD2": (("GTF2IRD2B", "7", 66.7, 62.5, True),),
    "GTF2IRD2B": (("GTF2IRD2", "7", 67.5, 82.5, True),),
    "H2AB1": (("H2AB2", "X", 1.7, 77.3, True), ("H2AB3", "X", 1.7, 77.3, True),),
    "H2AB2": (("H2AB1", "X", 1.7, 78.3, True), ("H2AB3", "X", 1.7, 78.3, True),),
    "H2AB3": (("H2AB1", "X", 1.7, 78.3, True), ("H2AB2", "X", 1.7, 78.3, True),),
    "HAVCR1": (("HAVCR1P1", "19", 0, 14.2, False),),
    "HBA1": (("HBA2", "16", 60.8, 100.0, True),),
    "HBA2": (("HBA1", "16", 60.8, 100.0, True),),
    "HBG1": (("HBG2", "11", 34.2, 76.1, True),),
    "HBG2": (("HBG1", "11", 33.3, 77.0, True),),
    "HCAR2": (("HCAR3", "12", 33.3, 33.3, True),),
    "HCAR3": (("HCAR2", "12", 31.7, 31.7, True),),
    "HERC2": (("HERC2P3", "15", 9.2, 15.0, False), ("HERC2P2", "15", 10.0, 13.3, False),),
    "HLA-A": (("HLA-C", "6", 0, 10.0, True), ("HLA-G", "6", 0, 10.0, True),),
    "HLA-B": (("HLA-C", "6", 2.5, 17.5, True), ("HLA-A", "6", 0, 11.7, True),),
    "HLA-C": (("HLA-B", "6", 2.5, 15.8, True), ("HLA-A", "6", 0, 11.7, True),),
    "HLA-DQA1": (("HLA-DQA2", "6", 0.8, 29.2, True),),
    "HLA-DQA2": (("HLA-DQA1", "6", 1.7, 33.3, True),),
    "HLA-DRB1": (("HLA-DRB5", "6", 0.8, 20.8, True),),
    "HLA-DRB5": (("HLA-DRB1", "6", 0.8, 17.5, True),),
    "HLA-G": (("HLA-A", "6", 0, 12.5, True),),
    "HNRNPA1": (("HNRNPA1P10", "19", 0, 11.7, False),),
    "HNRNPCL1": (("HNRNPCL2", "1", 68.3, 77.5, True), ("HNRNPCL3", "1", 68.3, 77.5, True), ("HNRNPCL4", "1", 68.3, 77.5, True),),
    "HNRNPCL2": (("HNRNPCL1", "1", 68.3, 77.5, True),),
    "HNRNPCL3": (("HNRNPCL1", "1", 51.7, 39.2, True),),
    "HNRNPCL4": (("HNRNPCL1", "1", 54.2, 35.8, True),),
    "HS3ST3A1": (("HS3ST3B1", "17", 0, 10.8, True),),
    "HS3ST3B1": (("HS3ST3A1", "17", 0, 15.0, True),),
    "HSD17B7": (("HSD17B7P2", "10", 34.2, 16.7, False),),
    "HSD3B1": (("HSD3B2", "1", 1.7, 24.2, True),),
    "HSD3B2": (("HSD3B1", "1", 0.8, 20.8, True),),
    "HSFX3": (("HSFX4", "X", 95.0, 97.5, True),),
    "HSFX4": (("HSFX3", "X", 95.0, 97.5, True),),
    "HSP90B1": (("HSP90B2P", "15", 0, 10.8, False),),
    "HSPA1A": (("HSPA1B", "6", 87.5, 87.5, True), ("HSPA1L", "6", 26.7, 0, True),),
    "HSPA1B": (("HSPA1A", "6", 81.7, 81.7, True), ("HSPA1L", "6", 18.3, 0, True),),
    "HSPA6": (("HSPA7", "1", 42.5, 42.5, False),),
    "ICAM4": (("ICAM1", "19", 40.8, 0, True),),
    "IFITM2": (("IFITM3", "11", 50.8, 0, True),),
    "IFITM3": (("IFITM2", "11", 58.3, 0, True),),
    "IFNA1": (("IFNA13", "9", 61.7, 85.0, True),),
    "IFNA10": (("IFNA4", "9", 66.7, 66.7, True), ("IFNA7", "9", 49.2, 33.3, True), ("IFNA17", "9", 47.5, 47.5, True),),
    "IFNA13": (("IFNA1", "9", 100.0, 100.0, True),),
    "IFNA14": (("IFNA4", "9", 13.3, 13.3, True), ("IFNA10", "9", 11.7, 11.7, True), ("IFNA16", "9", 10.0, 10.0, True),),
    "IFNA16": (("IFNA7", "9", 26.7, 2.5, True), ("IFNA17", "9", 19.2, 19.2, True), ("IFNA4", "9", 19.2, 19.2, True),),
    "IFNA17": (("IFNA10", "9", 53.3, 53.3, True), ("IFNA4", "9", 52.5, 52.5, True), ("IFNA7", "9", 48.3, 34.2, True),),
    "IFNA21": (("IFNA10", "9", 16.7, 16.7, True), ("IFNA4", "9", 16.7, 16.7, True), ("IFNA7", "9", 15.8, 15.8, True),),
    "IFNA4": (("IFNA10", "9", 67.5, 67.5, True), ("IFNA7", "9", 54.2, 42.5, True), ("IFNA17", "9", 50.8, 50.8, True),),
    "IFNA5": (("IFNA21", "9", 16.7, 16.7, True),),
    "IFNA7": (("IFNA10", "9", 83.3, 83.3, True), ("IFNA4", "9", 83.3, 83.3, True), ("IFNA17", "9", 50.0, 50.0, True),),
    "IFNL2": (("IFNL3", "19", 45.8, 33.3, True),),
    "IFNL3": (("IFNL2", "19", 35.8, 65.8, True),),
    "INTS4": (("INTS4P1", "7", 11.7, 22.5, False), ("INTS4P2", "7", 9.2, 11.7, False),),
    "ITLN1": (("ITLN2", "1", 0, 15.0, True),),
    "ITLN2": (("ITLN1", "1", 0, 15.8, True),),
    "KBTBD6": (("KBTBD7", "13", 14.2, 14.2, True),),
    "KBTBD7": (("KBTBD6", "13", 17.5, 17.5, True),),
    "KIR2DL1": (("KIR2DL3", "19", 32.5, 28.3, True), ("KIR2DS4", "19", 19.2, 9.2, True),),
    "KIR2DL3": (("KIR2DL1", "19", 30.8, 27.5, True), ("KIR2DS4", "19", 20.0, 15.8, True),),
    "KIR2DS4": (("KIR2DL3", "19", 14.2, 13.3, True), ("KIR2DL1", "19", 13.3, 7.5, True),),
    "KIR3DL1": (("KIR3DL2", "19", 12.5, 21.7, True),),
    "KIR3DL2": (("KIR3DL1", "19", 7.5, 20.8, True),),
    "KLRC2": (("KLRC3", "12", 22.5, 0, True),),
    "KLRC3": (("KLRC2", "12", 15.0, 0.8, True),),
    "KRTAP10-1": (("KRTAP10-5", "21", 12.5, 12.5, True),),
    "KRTAP10-10": (("KRTAP10-6", "21", 20.8, 20.8, True),),
    "KRTAP10-2": (("KRTAP10-9", "21", 13.3, 0, True),),
    "KRTAP10-4": (("KRTAP10-7", "21", 25.8, 17.5, True), ("KRTAP10-6", "21", 20.8, 20.8, True),),
    "KRTAP10-5": (("KRTAP10-1", "21", 12.5, 12.5, True),),
    "KRTAP10-6": (("KRTAP10-4", "21", 27.5, 27.5, True), ("KRTAP10-7", "21", 20.8, 24.2, True),),
    "KRTAP10-7": (("KRTAP10-4", "21", 25.8, 15.0, True), ("KRTAP10-6", "21", 16.7, 21.7, True),),
    "KRTAP10-9": (("KRTAP10-2", "21", 15.8, 0, True),),
    "KRTAP13-1": (("KRTAP13-2", "21", 17.5, 17.5, True),),
    "KRTAP4-11": (("KRTAP4-9", "17", 17.5, 17.5, True),),
    "KRTAP4-9": (("KRTAP4-11", "17", 14.2, 14.2, True),),
    "KRTAP5-8": (("KRTAP5-3", "11", 19.2, 5.8, True),),
    "KRTAP9-2": (("KRTAP9-9", "17", 61.7, 31.7, True), ("KRTAP9-8", "17", 60.8, 60.8, True), ("KRTAP9-3", "17", 16.7, 16.7, True),),
    "KRTAP9-3": (("KRTAP9-2", "17", 16.7, 16.7, True), ("KRTAP9-8", "17", 16.7, 16.7, True),),
    "KRTAP9-7": (("KRTAP9-9", "17", 100.0, 100.0, True), ("KRTAP9-2", "17", 90.9, 90.9, True),),
    "KRTAP9-8": (("KRTAP9-2", "17", 60.0, 60.0, True), ("KRTAP9-3", "17", 16.7, 16.7, True),),
    "KRTAP9-9": (("KRTAP9-2", "17", 5.8, 29.2, True), ("KRTAP9-7", "17", 1.7, 10.0, True),),
    "LAIR1": (("LAIR2", "19", 11.7, 0, True),),
    "LAIR2": (("LAIR1", "19", 24.2, 0, True),),
    "LCE1E": (("LCE1D", "1", 15.0, 0, True),),
    "LEFTY1": (("LEFTY2", "1", 8.3, 25.8, True),),
    "LEFTY2": (("LEFTY1", "1", 5.8, 15.0, True),),
    "LGALS7": (("LGALS7B", "19", 95.0, 0, True),),
    "LGALS7B": (("LGALS7", "19", 95.0, 0, True),),
    "LGALS9": (("LGALS9B", "17", 2.5, 45.0, True), ("LGALS9C", "17", 3.3, 32.5, True),),
    "LGALS9B": (("LGALS9C", "17", 79.2, 61.7, True), ("LGALS9", "17", 5.0, 45.8, True),),
    "LGALS9C": (("LGALS9B", "17", 75.8, 58.3, True), ("LGALS9", "17", 5.0, 34.2, True),),
    "LILRA1": (("LILRB1", "19", 2.5, 10.8, True), ("LILRA3", "19", 7.5, 10.0, True),),
    "LILRA3": (("LILRB1", "19", 4.2, 22.5, True), ("LILRA1", "19", 10.0, 21.7, True), ("LILRB2", "19", 3.3, 15.8, True),),
    "LILRB1": (("LILRA3", "19", 0.8, 10.8, True),),
    "LILRB2": (("LILRB1", "19", 14.2, 1.7, True),),
    "LIMS1": (("LIMS4", "2", 8.3, 15.0, True),),
    "LIMS3": (("LIMS4", "2", 97.5, 44.2, True), ("LIMS1", "2", 41.7, 9.2, True),),
    "LIMS4": (("LIMS3", "2", 98.3, 54.2, True), ("LIMS1", "2", 45.8, 37.5, True),),
    "LRRC37A2": (("LRRC37A3", "17", 53.3, 80.8, True), ("LRRC37A6P", "10", 1.7, 10.8, False),),
    "LRRC37A3": (("LRRC37A2", "17", 40.0, 68.3, True), ("LRRC37A6P", "10", 0.8, 10.0, False),),
    "LYPLA2": (("LYPLA2P2", "19", 0, 10.0, False),),
    "LYZL1": (("LYZL2", "10", 3.3, 67.5, True),),
    "LYZL2": (("LYZL1", "10", 4.2, 50.8, True),),
    "MBD3L2": (("MBD3L2B", "19", 98.3, 89.2, True), ("MBD3L4", "19", 10.0, 89.2, True), ("MBD3L5", "19", 10.0, 89.2, True),),
    "MBD3L2B": (("MBD3L2", "19", 90.0, 45.8, True), ("MBD3L4", "19", 10.8, 38.3, True), ("MBD3L5", "19", 10.8, 38.3, True),),
    "MBD3L3": (("MBD3L4", "19", 97.5, 83.3, True), ("MBD3L2", "19", 15.0, 90.0, True), ("MBD3L5", "19", 87.5, 83.3, True),),
    "MBD3L4": (("MBD3L5", "19", 89.2, 100.0, True), ("MBD3L3", "19", 97.5, 83.3, True), ("MBD3L2", "19", 15.0, 90.0, True),),
    "MBD3L5": (("MBD3L4", "19", 88.3, 100.0, True), ("MBD3L2", "19", 13.3, 91.7, True), ("MBD3L3", "19", 86.7, 83.3, True),),
    "MEIS3": (("MEIS3P1", "17", 0, 25.0, False),),
    "MFSD14B": (("MFSD14C", "9", 34.2, 3.3, True),),
    "MFSD14C": (("MFSD14B", "9", 35.8, 33.3, True),),
    "MKRN1": (("MKRN9P", "12", 0, 10.8, False),),
    "MRGPRX1": (("MRGPRX3", "11", 10.0, 10.0, True),),
    "MRGPRX3": (("MRGPRX1", "11", 0.8, 19.2, True),),
    "MRGPRX4": (("MRGPRX3", "11", 15.0, 10.0, True),),
    "MS4A13": (("MS4A5", "11", 12.5, 0, True),),
    "MS4A5": (("MS4A13", "11", 16.7, 0, True),),
    "MST1": (("MST1L", "1", 40.8, 10.8, True), ("MST1P2", "1", 40.8, 10.0, False),),
    "MST1L": (("MST1P2", "1", 37.5, 5.0, False), ("MST1", "3", 16.7, 5.0, True),),
    "MSX2": (("MSX2P1", "17", 3.3, 10.0, False),),
    "MT1E": (("MT1JP", "16", 12.5, 0, False),),
    "MTRNR2L2": (("MTRNR2L8", "11", 40.0, 40.0, True),),
    "MTRNR2L8": (("MTRNR2L2", "5", 26.7, 26.7, True), ("MTRNR2L9", "6", 0.8, 15.0, True),),
    "MTRNR2L9": (("MTRNR2L1", "17", 100.0, 100.0, True),),
    "MYH1": (("MYH2", "17", 0.8, 28.3, True), ("MYH4", "17", 0, 16.7, True),),
    "MYH2": (("MYH1", "17", 0.8, 29.2, True), ("MYH4", "17", 0, 15.0, True),),
    "MYH4": (("MYH1", "17", 0, 16.7, True), ("MYH2", "17", 0, 10.8, True),),
    "MYH6": (("MYH7", "14", 0, 32.5, True),),
    "MYH7": (("MYH6", "14", 0, 32.5, True),),
    "MYL6": (("MYL6B", "12", 14.2, 0, True),),
    "MZT2A": (("MZT2B", "2", 16.7, 0, True),),
    "MZT2B": (("MZT2A", "2", 12.5, 0, True),),
    "NACA2": (("NACA", "12", 0, 28.3, True),),
    "NANOG": (("NANOGP8", "15", 7.5, 40.0, True),),
    "NANOGP8": (("NANOG", "12", 28.3, 35.8, True),),
    "NAPSA": (("NAPSB", "19", 0, 39.2, False),),
    "NAT8": (("NAT8B", "2", 8.3, 18.3, True),),
    "NAT8B": (("NAT8", "2", 30.0, 30.0, True),),
    "NBPF1": (("NBPF14", "1", 22.5, 41.7, True), ("NBPF12", "1", 26.7, 40.0, True), ("NBPF11", "1", 22.5, 36.7, True),),
    "NBPF10": (("NBPF14", "1", 9.5, 59.2, True), ("NBPF8", "1", 11.4, 56.7, True), ("NBPF15", "1", 10.5, 40.8, True),),
    "NBPF11": (("NBPF12", "1", 50.8, 53.3, True), ("NBPF8", "1", 32.5, 40.0, True), ("NBPF14", "1", 23.3, 40.0, True),),
    "NBPF12": (("NBPF11", "1", 57.5, 52.5, True), ("NBPF14", "1", 38.3, 48.3, True), ("NBPF8", "1", 40.0, 42.5, True),),
    "NBPF14": (("NBPF8", "1", 45.8, 53.3, True), ("NBPF12", "1", 35.8, 50.8, True), ("NBPF15", "1", 45.8, 38.3, True),),
    "NBPF15": (("NBPF8", "1", 46.7, 33.3, True), ("NBPF14", "1", 25.8, 42.5, True), ("NBPF12", "1", 36.7, 41.7, True),),
    "NBPF26": (("NBPF15", "1", 31.3, 56.7, True), ("NBPF8", "1", 35.8, 55.8, True), ("NBPF12", "1", 26.9, 54.2, True),),
    "NBPF3": (("NBPF1", "1", 13.3, 11.7, True), ("NBPF12", "1", 2.5, 10.0, True), ("NBPF15", "1", 1.7, 10.0, True),),
    "NBPF4": (("NBPF6", "1", 90.0, 75.8, True), ("NBPF22P", "5", 25.0, 23.3, False),),
    "NBPF6": (("NBPF4", "1", 89.2, 57.5, True), ("NBPF22P", "5", 33.3, 23.3, False),),
    "NBPF8": (("NBPF12", "1", 27.3, 36.7, True), ("NBPF14", "1", 13.6, 34.2, True), ("NBPF11", "1", 25.0, 31.7, True),),
    "NBPF9": (("NBPF14", "1", 6.2, 65.8, True), ("NBPF12", "1", 6.2, 58.3, True), ("NBPF15", "1", 4.2, 51.7, True),),
    "NCF1": (("NCF1C", "7", 66.7, 69.2, False), ("NCF1B", "7", 67.5, 3.3, False),),
    "NLRP2": (("NLRP7", "19", 1.7, 15.0, True),),
    "NLRP7": (("NLRP2", "19", 1.7, 16.7, True),),
    "NOC2L": (("NOC2LP2", "2", 0, 20.8, False),),
    "NOMO1": (("NOMO3", "16", 57.5, 90.8, True), ("NOMO2", "16", 58.3, 81.7, True),),
    "NOMO2": (("NOMO3", "16", 76.7, 92.5, True), ("NOMO1", "16", 60.0, 88.3, True),),
    "NOMO3": (("NOMO1", "16", 61.7, 92.5, True), ("NOMO2", "16", 74.2, 85.8, True),),
    "NOTCH2NLA": (("NOTCH2NLC", "1", 57.5, 74.2, True), ("NOTCH2NLR", "1", 55.0, 5.0, False),),
    "NOTCH2NLB": (("NOTCH2NLC", "1", 60.0, 67.5, True), ("NOTCH2NLR", "1", 55.0, 3.3, False),),
    "NOTCH2NLC": (("NOTCH2NLB", "1", 21.7, 63.3, True), ("NOTCH2NLR", "1", 60.0, 15.8, False), ("NOTCH2NLA", "1", 21.7, 42.5, True),),
    "NPEPPS": (("NPEPPSP1", "17", 17.5, 5.0, False),),
    "NPIPA1": (("NPIPA2", "16", 50.8, 87.5, True), ("NPIPA3", "16", 50.8, 87.5, True), ("NPIPA7", "16", 57.5, 76.7, True),),
    "NPIPA2": (("NPIPA1", "16", 25.8, 87.5, True), ("NPIPA8", "16", 30.8, 67.5, True), ("NPIPA7", "16", 30.0, 67.5, True),),
    "NPIPA3": (("NPIPA1", "16", 25.8, 87.5, True), ("NPIPA8", "16", 30.8, 67.5, True), ("NPIPA7", "16", 30.0, 67.5, True),),
    "NPIPA5": (("NPIPA2", "16", 51.7, 21.7, True), ("NPIPA3", "16", 51.7, 21.7, True), ("NPIPA7", "16", 50.8, 25.0, True),),
    "NPIPA7": (("NPIPA8", "16", 82.5, 100.0, True), ("NPIPA1", "16", 52.5, 60.8, True), ("NPIPA2", "16", 46.7, 54.2, True),),
    "NPIPA8": (("NPIPA7", "16", 75.8, 50.0, True), ("NPIPA1", "16", 46.7, 32.5, True), ("NPIPA5", "16", 44.2, 10.8, True),),
    "NPIPB11": (("NPIPB12", "16", 45.0, 29.2, True), ("NPIPB13", "16", 45.0, 25.8, True), ("NPIPB5", "16", 44.2, 23.3, True),),
    "NPIPB12": (("NPIPB13", "16", 79.2, 48.3, True), ("NPIPB3", "16", 62.5, 40.0, True), ("NPIPB5", "16", 62.5, 40.0, True),),
    "NPIPB13": (("NPIPB12", "16", 72.5, 35.0, True), ("NPIPB3", "16", 65.8, 30.0, True), ("NPIPB5", "16", 65.8, 30.0, True),),
    "NPIPB15": (("NPIPB8", "16", 44.2, 45.8, True), ("NPIPB9", "16", 41.7, 45.8, True), ("NPIPB6", "16", 40.8, 45.0, True),),
    "NPIPB2": (("NPIPA5", "16", 13.3, 0, True), ("NPIPB3", "16", 13.3, 11.7, True), ("NPIPB5", "16", 13.3, 11.7, True),),
    "NPIPB3": (("NPIPB5", "16", 73.3, 38.3, True), ("NPIPB4", "16", 66.7, 30.8, True), ("NPIPB12", "16", 58.3, 35.0, True),),
    "NPIPB4": (("NPIPB5", "16", 71.7, 26.7, True), ("NPIPB3", "16", 70.0, 25.8, True), ("NPIPB12", "16", 66.7, 25.8, True),),
    "NPIPB5": (("NPIPB3", "16", 77.5, 40.0, True), ("NPIPB4", "16", 71.7, 30.0, True), ("NPIPB12", "16", 65.0, 30.0, True),),
    "NPIPB6": (("NPIPB9", "16", 70.0, 60.8, True), ("NPIPB8", "16", 55.8, 61.7, True), ("NPIPB15", "16", 34.2, 50.8, True),),
    "NPIPB8": (("NPIPB9", "16", 62.5, 93.3, True), ("NPIPB6", "16", 57.5, 73.3, True), ("NPIPB15", "16", 38.3, 54.2, True),),
    "NPIPB9": (("NPIPB8", "16", 55.0, 74.2, True), ("NPIPB6", "16", 65.8, 53.3, True), ("NPIPB15", "16", 37.5, 40.8, True),),
    "NSUN5": (("NSUN5P2", "7", 6.7, 10.8, False),),
    "NUTM2A": (("NUTM2B", "10", 88.3, 85.8, True), ("NUTM2E", "10", 87.5, 83.3, True), ("NUTM2D", "10", 85.8, 79.2, True),),
    "NUTM2B": (("NUTM2E", "10", 90.8, 94.2, True), ("NUTM2A", "10", 90.0, 85.8, True), ("NUTM2D", "10", 87.5, 73.3, True),),
    "NUTM2D": (("NUTM2A", "10", 65.0, 82.5, True), ("NUTM2B", "10", 58.3, 75.0, True), ("NUTM2E", "10", 54.2, 71.7, True),),
    "NUTM2E": (("NUTM2B", "10", 37.5, 40.8, True), ("NUTM2A", "10", 32.5, 35.8, True), ("NUTM2D", "10", 30.8, 30.0, True),),
    "NUTM2F": (("NUTM2G", "9", 60.0, 74.2, True),),
    "NUTM2G": (("NUTM2F", "9", 52.5, 70.8, True),),
    "NXF2": (("NXF5", "X", 0.8, 24.2, True),),
    "NXF2B": (("NXF5", "X", 2.5, 22.5, True),),
    "NXF5": (("NXF2", "X", 9.2, 25.8, True), ("NXF2B", "X", 9.2, 25.8, True),),
    "OBP2A": (("OBP2B", "9", 20.8, 0, True),),
    "OBP2B": (("OBP2A", "9", 18.3, 0, True),),
    "OCLN": (("OCLNP1", "5", 24.2, 5.0, False),),
    "OCM": (("OCM2", "7", 16.7, 23.3, True),),
    "OCM2": (("OCM", "7", 17.5, 100.0, True),),
    "OPN1LW": (("OPN1MW", "X", 78.3, 66.7, True),),
    "OPN1MW": (("OPN1LW", "X", 49.2, 51.7, True),),
    "OR11H1": (("OR11H12", "14", 92.5, 92.5, True), ("OR11H2", "14", 88.3, 88.3, True),),
    "OR11H12": (("OR11H1", "22", 91.7, 91.7, True), ("OR11H2", "14", 87.5, 87.5, True),),
    "OR11H2": (("OR11H1", "22", 65.0, 81.7, True), ("OR11H12", "14", 62.5, 80.8, True),),
    "OR13C2": (("OR13C5", "9", 51.7, 51.7, True), ("OR13C9", "9", 17.5, 17.5, True),),
    "OR13C3": (("OR13C4", "9", 11.7, 11.7, True),),
    "OR13C5": (("OR13C2", "9", 51.7, 51.7, True), ("OR13C9", "9", 11.7, 11.7, True),),
    "OR13C9": (("OR13C2", "9", 17.5, 17.5, True), ("OR13C5", "9", 11.7, 11.7, True),),
    "OR3A2": (("OR3A3", "17", 48.3, 48.3, True),),
    "OR3A3": (("OR3A2", "17", 83.3, 83.3, True),),
    "ORM1": (("ORM2", "9", 38.3, 22.5, True),),
    "ORM2": (("ORM1", "9", 37.5, 22.5, True),),
    "OTOA": (("OTOAP1", "16", 20.8, 27.5, False),),
    "OXCT2": (("OXCT2P1", "1", 68.3, 68.3, False),),
    "PA2G4": (("PA2G4P4", "3", 0, 12.5, False),),
    "PABPC1": (("PABPC3", "13", 0, 14.2, True),),
    "PABPC1L2A": (("PABPC1L2B", "X", 75.0, 75.0, True),),
    "PABPC1L2B": (("PABPC1L2A", "X", 60.8, 49.2, True),),
    "PABPC3": (("PABPC1", "8", 0, 14.2, True),),
    "PAGE2": (("PAGE2B", "X", 45.0, 26.2, True),),
    "PAGE2B": (("PAGE2", "X", 49.2, 26.8, True),),
    "PDCL3": (("PDCL3P4", "3", 0, 10.0, False),),
    "PDIA3": (("PDIA3P1", "1", 0, 25.0, False),),
    "PDZK1": (("PDZK1P1", "1", 22.5, 40.8, False),),
    "PGA3": (("PGA4", "11", 90.8, 100.0, True), ("PGA5", "11", 67.5, 86.7, True),),
    "PGA4": (("PGA3", "11", 92.5, 99.2, True), ("PGA5", "11", 78.3, 94.2, True),),
    "PGA5": (("PGA4", "11", 71.7, 94.2, True), ("PGA3", "11", 65.8, 93.3, True),),
    "PGAM1": (("PGAM4", "X", 0.8, 38.3, True),),
    "PGAM4": (("PGAM1", "10", 6.7, 35.8, True),),
    "PGM5": (("PGM5P2", "9", 15.8, 19.2, False),),
    "PI4KA": (("PI4KAP2", "22", 5.8, 10.8, False), ("PI4KAP1", "22", 5.0, 10.0, False),),
    "PIGBOS1": (("PIGB", "15", 27.5, 0, True),),
    "PILRA": (("PILRB", "7", 0, 19.2, True),),
    "PILRB": (("PILRA", "7", 3.3, 13.3, True),),
    "PKD1": (("PKD1P1", "16", 11.7, 15.0, False),),
    "PLGLB1": (("PLGLB2", "2", 85.8, 85.0, True), ("PLGLA", "2", 34.2, 5.8, False), ("PLG", "6", 19.2, 0.8, True),),
    "PLGLB2": (("PLGLB1", "2", 85.0, 85.8, True), ("PLGLA", "2", 35.8, 0, False), ("PLG", "6", 20.0, 0.8, True),),
    "PMS2": (("PMS2CL", "7", 20.0, 10.8, False),),
    "POLR2J2": (("POLR2J3", "7", 79.2, 59.2, True), ("POLR2J4", "7", 36.7, 20.0, False),),
    "POLR2J3": (("POLR2J2", "7", 71.7, 70.8, True), ("POLR2J4", "7", 34.2, 28.3, False),),
    "POM121": (("POM121C", "7", 18.3, 42.5, True),),
    "POM121C": (("POM121", "7", 20.0, 44.2, True),),
    "POTEB": (("POTEB3", "15", 89.2, 98.3, True), ("POTEB2", "15", 89.2, 90.0, True), ("POTED", "21", 33.3, 65.8, True),),
    "POTEB2": (("POTEB", "15", 85.8, 100.0, True), ("POTEB3", "15", 85.8, 100.0, True), ("POTED", "21", 40.8, 77.5, True),),
    "POTEB3": (("POTEB", "15", 79.2, 30.8, True), ("POTEB2", "15", 79.2, 27.5, True), ("POTED", "21", 36.7, 41.7, True),),
    "POTEC": (("POTED", "21", 43.3, 61.7, True), ("POTEB3", "15", 27.5, 56.7, True), ("POTEB", "15", 25.0, 56.7, True),),
    "POTED": (("POTEC", "18", 50.0, 20.0, True), ("POTEB3", "15", 34.2, 41.7, True), ("POTEB", "15", 32.5, 19.2, True),),
    "POTEE": (("POTEF", "2", 66.7, 72.5, True), ("POTEJ", "2", 37.5, 60.8, True), ("POTEI", "2", 31.7, 56.7, True),),
    "POTEF": (("POTEE", "2", 68.3, 79.2, True), ("POTEI", "2", 26.7, 64.2, True), ("POTEJ", "2", 29.2, 55.8, True),),
    "POTEG": (("POTEM", "14", 78.3, 59.2, True), ("POTEH", "22", 65.8, 56.7, True), ("POTEF", "2", 5.8, 30.8, True),),
    "POTEH": (("POTEM", "14", 71.7, 88.3, True), ("POTEG", "14", 67.5, 62.5, True), ("POTEI", "2", 7.5, 30.0, True),),
    "POTEI": (("POTEJ", "2", 59.2, 35.8, True), ("POTEE", "2", 33.3, 37.5, True), ("POTEF", "2", 35.8, 35.0, True),),
    "POTEJ": (("POTEI", "2", 70.0, 74.2, True), ("POTEE", "2", 38.3, 71.7, True), ("POTEF", "2", 35.8, 69.2, True),),
    "POTEM": (("POTEG", "14", 70.8, 14.2, True), ("POTEH", "22", 68.3, 20.0, True), ("POTEI", "2", 5.0, 18.3, True),),
    "POU5F1": (("POU5F1P4", "1", 0, 41.7, False), ("POU5F1B", "8", 0, 20.0, True), ("POU5F1P3", "12", 1.7, 12.5, False),),
    "POU5F1B": (("POU5F1", "6", 0, 24.2, True), ("POU5F1P4", "1", 14.2, 14.2, False),),
    "PPIAL4A": (("PPIAL4C", "1", 100.0, 100.0, True), ("PPIAL4H", "1", 100.0, 100.0, True), ("PPIAL4D", "1", 80.8, 80.8, True),),
    "PPIAL4C": (("PPIAL4A", "1", 100.0, 47.5, True), ("PPIAL4H", "1", 100.0, 100.0, True), ("PPIAL4G", "1", 84.2, 81.7, True),),
    "PPIAL4D": (("PPIAL4E", "1", 100.0, 100.0, True), ("PPIAL4F", "1", 100.0, 100.0, True), ("PPIAL4G", "1", 73.3, 70.8, True),),
    "PPIAL4E": (("PPIAL4D", "1", 100.0, 100.0, True), ("PPIAL4F", "1", 100.0, 100.0, True), ("PPIAL4G", "1", 73.3, 70.8, True),),
    "PPIAL4F": (("PPIAL4D", "1", 100.0, 100.0, True), ("PPIAL4E", "1", 100.0, 100.0, True), ("PPIAL4G", "1", 73.3, 70.8, True),),
    "PPIAL4G": (("PPIAL4A", "1", 81.7, 40.8, True), ("PPIAL4C", "1", 81.7, 81.7, True), ("PPIAL4H", "1", 81.7, 81.7, True),),
    "PPIAL4H": (("PPIAL4C", "1", 49.2, 17.5, True), ("PPIAL4A", "1", 43.3, 11.7, True), ("PPIAL4D", "1", 40.8, 11.7, True),),
    "PRDM7": (("PRDM9", "5", 5.8, 15.8, True),),
    "PRDM9": (("PRDM7", "16", 5.8, 15.0, True),),
    "PRR23D1": (("PRR23D2", "8", 99.2, 100.0, True),),
    "PRR23D2": (("PRR23D1", "8", 99.2, 100.0, True),),
    "PRY": (("PRY2", "Y", 90.0, 100.0, True),),
    "PRY2": (("PRY", "Y", 90.0, 100.0, True),),
    "PSG1": (("PSG3", "19", 17.5, 33.3, True), ("PSG8", "19", 15.8, 31.7, True), ("PSG7", "19", 10.0, 29.2, True),),
    "PSG11": (("PSG2", "19", 15.8, 38.3, True), ("PSG3", "19", 15.0, 13.3, True), ("PSG10P", "19", 12.5, 2.5, False),),
    "PSG2": (("PSG11", "19", 14.2, 37.5, True), ("PSG1", "19", 7.5, 15.0, True), ("PSG5", "19", 14.2, 13.3, True),),
    "PSG3": (("PSG8", "19", 16.7, 36.7, True), ("PSG1", "19", 9.2, 33.3, True), ("PSG7", "19", 7.5, 27.5, True),),
    "PSG4": (("PSG8", "19", 7.5, 30.8, True), ("PSG7", "19", 6.7, 23.3, True), ("PSG1", "19", 5.8, 20.0, True),),
    "PSG5": (("PSG10P", "19", 11.7, 20.8, False), ("PSG2", "19", 11.7, 13.3, True), ("PSG11", "19", 10.0, 3.3, True),),
    "PSG6": (("PSG9", "19", 10.0, 35.0, True), ("PSG3", "19", 9.2, 19.2, True), ("PSG1", "19", 3.3, 19.2, True),),
    "PSG7": (("PSG8", "19", 10.0, 35.0, True), ("PSG3", "19", 11.7, 25.8, True), ("PSG1", "19", 10.8, 25.8, True),),
    "PSG8": (("PSG7", "19", 10.8, 34.2, True), ("PSG3", "19", 20.0, 32.5, True), ("PSG1", "19", 15.0, 31.7, True),),
    "PSG9": (("PSG6", "19", 7.5, 33.3, True), ("PSG3", "19", 12.5, 23.3, True), ("PSG1", "19", 9.2, 20.8, True),),
    "PTTG1": (("PTTG3P", "8", 0, 45.8, False), ("PTTG2", "4", 0, 16.7, True),),
    "PTTG2": (("PTTG3P", "8", 18.3, 15.8, False), ("PTTG1", "5", 0, 16.7, True),),
    "PVRIG": (("PVRIG2P", "7", 32.5, 23.3, False),),
    "RABL2A": (("RABL2B", "22", 50.0, 68.3, True),),
    "RABL2B": (("RABL2A", "2", 53.3, 17.5, True),),
    "RAET1G": (("RAET1L", "6", 3.3, 20.8, True),),
    "RAET1L": (("RAET1G", "6", 4.2, 16.7, True),),
    "RALGAPA1": (("RALGAPA1P1", "9", 0, 50.8, False),),
    "RASA4": (("RASA4B", "7", 76.7, 78.3, True), ("RASA4DP", "7", 24.2, 49.2, False), ("RASA4CP", "7", 17.5, 15.8, False),),
    "RASA4B": (("RASA4", "7", 78.3, 70.0, True), ("RASA4DP", "7", 26.7, 43.3, False), ("RASA4CP", "7", 15.0, 15.0, False),),
    "RBMY1B": (("RBMY1D", "Y", 92.5, 65.0, True), ("RBMY1E", "Y", 73.3, 91.7, True), ("RBMY1J", "Y", 58.3, 84.2, True),),
    "RBMY1D": (("RBMY1B", "Y", 92.5, 64.2, True), ("RBMY1E", "Y", 89.2, 66.7, True), ("RBMY1F", "Y", 76.7, 33.3, True),),
    "RBMY1E": (("RBMY1B", "Y", 91.7, 94.2, True), ("RBMY1D", "Y", 92.5, 65.0, True), ("RBMY1J", "Y", 75.8, 90.8, True),),
    "RBMY1F": (("RBMY1B", "Y", 14.2, 65.8, True), ("RBMY1E", "Y", 14.2, 65.8, True), ("RBMY1D", "Y", 14.2, 43.3, True),),
    "RBMY1J": (("RBMY1E", "Y", 78.3, 85.0, True), ("RBMY1B", "Y", 75.0, 85.0, True), ("RBMY1D", "Y", 82.5, 51.7, True),),
    "REG1A": (("REG1B", "2", 0, 15.8, True),),
    "REG1B": (("REG1A", "2", 0, 12.5, True),),
    "REG3A": (("REG3G", "2", 0, 13.3, True),),
    "REG3G": (("REG3A", "2", 0, 15.8, True),),
    "RFPL1": (("RFPL2", "22", 8.3, 34.2, True), ("RFPL3", "22", 9.2, 32.5, True), ("RFPL3S", "22", 6.7, 12.5, False),),
    "RFPL2": (("RFPL3", "22", 2.5, 31.7, True), ("RFPL1", "22", 2.5, 28.3, True),),
    "RFPL3": (("RFPL1", "22", 4.2, 52.5, True), ("RFPL2", "22", 8.3, 48.3, True), ("RFPL1S", "22", 4.2, 24.2, False),),
    "RGPD1": (("RGPD2", "2", 63.3, 85.0, True), ("RGPD5", "2", 18.3, 46.7, True), ("RGPD8", "2", 18.3, 46.7, True),),
    "RGPD2": (("RGPD1", "2", 73.3, 100.0, True), ("RGPD3", "2", 24.2, 59.2, True), ("RGPD5", "2", 23.3, 59.2, True),),
    "RGPD3": (("RGPD4", "2", 67.5, 82.5, True), ("RGPD5", "2", 37.5, 65.8, True), ("RGPD8", "2", 37.5, 65.8, True),),
    "RGPD4": (("RGPD3", "2", 63.3, 88.3, True), ("RGPD5", "2", 36.7, 69.2, True), ("RGPD8", "2", 36.7, 69.2, True),),
    "RGPD5": (("RGPD6", "2", 94.2, 100.0, True), ("RGPD8", "2", 72.5, 98.3, True), ("RGPD3", "2", 31.7, 70.0, True),),
    "RGPD6": (("RGPD8", "2", 64.2, 100.0, True), ("RGPD5", "2", 65.8, 99.2, True), ("RGPD3", "2", 16.7, 66.7, True),),
    "RGPD8": (("RGPD6", "2", 94.2, 100.0, True), ("RGPD5", "2", 71.7, 95.8, True), ("RGPD3", "2", 31.7, 70.0, True),),
    "RLN1": (("RLN2", "9", 33.3, 0, True),),
    "RLN2": (("RLN1", "9", 34.2, 0, True),),
    "ROCK1": (("ROCK1P1", "18", 3.3, 14.2, False),),
    "ROPN1": (("ROPN1B", "3", 16.7, 23.3, True),),
    "ROPN1B": (("ROPN1", "3", 23.3, 49.2, True),),
    "RP9": (("RP9P", "7", 1.7, 48.3, False),),
    "RPS4Y1": (("RPS4Y2", "Y", 0, 19.2, True),),
    "RPS4Y2": (("RPS4Y1", "Y", 0, 20.8, True),),
    "RPSA": (("RPSAP58", "19", 0, 50.0, True), ("RPSAP9", "9", 0, 25.0, False),),
    "RPSAP58": (("RPSAP9", "9", 0, 29.2, False), ("RPSA", "3", 0, 24.2, True),),
    "RRN3": (("RRN3P2", "16", 24.2, 9.2, False), ("RRN3P1", "16", 20.0, 0, False), ("RRN3P3", "16", 11.7, 5.0, False),),
    "RRP7A": (("RRP7BP", "22", 20.0, 5.0, False),),
    "RTL8C": (("RTL8B", "X", 18.3, 18.3, True),),
    "SAA1": (("SAA2", "11", 35.0, 0, True),),
    "SAA2": (("SAA1", "11", 10.0, 0, True),),
    "SAFB": (("SAFB2", "19", 3.3, 10.0, True),),
    "SBDS": (("SBDSP1", "7", 10.8, 0, False),),
    "SDHA": (("SDHAP3", "5", 10.0, 0, False),),
    "SEMG1": (("SEMG2", "20", 10.0, 19.2, True),),
    "SEMG2": (("SEMG1", "20", 9.2, 14.2, True),),
    "SERF1A": (("SERF1B", "5", 86.7, 100.0, True),),
    "SERF1B": (("SERF1A", "5", 85.8, 100.0, True),),
    "SERHL2": (("SERHL", "22", 25.0, 24.2, False),),
    "SET": (("SETSIP", "1", 0, 10.0, True),),
    "SETSIP": (("SET", "9", 0, 39.2, True),),
    "SFTPA1": (("SFTPA2", "10", 27.5, 30.8, True),),
    "SFTPA2": (("SFTPA1", "10", 32.5, 26.7, True),),
    "SHLD2": (("SHLD2P3", "10", 14.2, 30.0, False), ("SHLD2P1", "10", 15.0, 13.3, False),),
    "SIGLEC11": (("SIGLEC16", "19", 10.0, 5.8, True),),
    "SIGLEC14": (("SIGLEC5", "19", 17.5, 15.8, True),),
    "SIGLEC16": (("SIGLEC11", "19", 21.7, 3.3, True),),
    "SIGLEC5": (("SIGLEC14", "19", 2.5, 10.0, True),),
    "SIRPG": (("SIRPB1", "20", 0, 12.5, True),),
    "SLC2A14": (("SLC2A3", "12", 0.8, 25.0, True),),
    "SLC2A3": (("SLC2A14", "12", 5.0, 26.7, True),),
    "SLC6A8": (("SLC6A10P", "16", 13.3, 0.8, False),),
    "SLCO1B7": (("SLCO1B3", "12", 0, 11.7, True),),
    "SLFN11": (("SLFN13", "17", 3.3, 14.2, True),),
    "SLX1A": (("SLX1B", "16", 97.5, 100.0, True),),
    "SLX1B": (("SLX1A", "16", 97.5, 94.2, True),),
    "SMG1": (("SMG1P1", "16", 9.2, 11.7, False),),
    "SMN1": (("SMN2", "5", 85.0, 95.8, True),),
    "SMN2": (("SMN1", "5", 85.0, 95.8, True),),
    "SMPD4": (("SMPD4BP", "2", 12.5, 37.5, False),),
    "SORD": (("SORD2P", "15", 24.2, 25.0, False),),
    "SPAG11A": (("SPAG11B", "8", 70.0, 70.0, True),),
    "SPAG11B": (("SPAG11A", "8", 74.2, 83.3, True),),
    "SPANXA1": (("SPANXD", "X", 28.3, 0, True), ("SPANXC", "X", 25.8, 0, True), ("SPANXB1", "X", 19.2, 0, True),),
    "SPANXA2": (("SPANXD", "X", 28.3, 0, True), ("SPANXC", "X", 25.8, 0, True), ("SPANXB1", "X", 20.0, 0, True),),
    "SPANXB1": (("SPANXA1", "X", 13.3, 0, True), ("SPANXA2", "X", 13.3, 0, True), ("SPANXD", "X", 12.5, 0, True),),
    "SPANXC": (("SPANXB1", "X", 92.5, 0, True), ("SPANXA1", "X", 88.3, 0, True), ("SPANXA2", "X", 88.3, 0, True),),
    "SPANXD": (("SPANXA1", "X", 91.7, 0, True), ("SPANXA2", "X", 91.7, 0, True), ("SPANXB1", "X", 65.0, 0, True),),
    "SPATA31A1": (("SPATA31A5", "9", 80.8, 86.7, True), ("SPATA31A7", "9", 80.8, 86.7, True), ("SPATA31A3", "9", 81.7, 85.8, True),),
    "SPATA31A3": (("SPATA31A5", "9", 90.0, 92.5, True), ("SPATA31A7", "9", 90.0, 92.5, True), ("SPATA31A1", "9", 82.5, 88.3, True),),
    "SPATA31A5": (("SPATA31A7", "9", 10.3, 96.7, True), ("SPATA31A3", "9", 8.0, 95.0, True), ("SPATA31A1", "9", 10.3, 86.7, True),),
    "SPATA31A6": (("SPATA31A1", "9", 75.0, 80.8, True), ("SPATA31A3", "9", 73.3, 78.3, True), ("SPATA31A5", "9", 74.2, 77.5, True),),
    "SPATA31A7": (("SPATA31A5", "9", 10.3, 97.5, True), ("SPATA31A3", "9", 6.9, 95.0, True), ("SPATA31A1", "9", 8.0, 85.0, True),),
    "SPATA31C1": (("SPATA31C2", "9", 64.2, 74.2, True), ("SPATA31A1", "9", 9.2, 17.5, True), ("SPATA31A3", "9", 9.2, 17.5, True),),
    "SPATA31C2": (("SPATA31C1", "9", 45.8, 77.5, True), ("SPATA31A6", "9", 7.5, 20.0, True), ("SPATA31A1", "9", 5.8, 17.5, True),),
    "SPATA31D1": (("SPATA31D3", "9", 22.5, 20.8, True), ("SPATA31D4", "9", 22.5, 22.5, True), ("SPATA31D5P", "9", 15.8, 17.5, False),),
    "SPATA31D3": (("SPATA31D4", "9", 84.2, 85.8, True), ("SPATA31D5P", "9", 20.8, 31.7, False), ("SPATA31D1", "9", 15.0, 27.5, True),),
    "SPATA31D4": (("SPATA31D3", "9", 84.2, 85.8, True), ("SPATA31D5P", "9", 33.3, 41.7, False), ("SPATA31D1", "9", 21.7, 27.5, True),),
    "SPIN2A": (("SPIN2B", "X", 60.8, 0, True),),
    "SPIN2B": (("SPIN2A", "X", 65.0, 0, True),),
    "SPRR2A": (("SPRR2B", "1", 30.8, 0, True), ("SPRR2E", "1", 19.2, 0, True), ("SPRR2F", "1", 19.2, 0, True),),
    "SPRR2B": (("SPRR2E", "1", 48.3, 0, True), ("SPRR2A", "1", 30.0, 0, True), ("SPRR2F", "1", 14.2, 0, True),),
    "SPRR2D": (("SPRR2B", "1", 11.7, 0, True), ("SPRR2E", "1", 10.8, 4.2, True), ("SPRR2A", "1", 10.0, 0, True),),
    "SPRR2E": (("SPRR2B", "1", 49.2, 0, True), ("SPRR2A", "1", 19.2, 0, True), ("SPRR2F", "1", 18.3, 0, True),),
    "SRGAP2B": (("SRGAP2D", "1", 65.0, 25.8, False),),
    "SRGAP2C": (("SRGAP2D", "1", 56.7, 28.3, False),),
    "SSX1": (("SSX8P", "X", 20.0, 0, False),),
    "SSX3": (("SSX2", "X", 17.5, 8.3, True), ("SSX2B", "X", 17.5, 8.3, True), ("SSX7", "X", 5.0, 15.8, True),),
    "SSX4": (("SSX7", "X", 1.7, 33.3, True), ("SSX5", "X", 1.7, 27.5, True), ("SSX3", "X", 3.3, 20.0, True),),
    "SSX4B": (("SSX7", "X", 1.7, 28.3, True), ("SSX5", "X", 1.7, 25.0, True), ("SSX3", "X", 4.2, 17.5, True),),
    "SSX5": (("SSX4", "X", 4.2, 20.0, True), ("SSX4B", "X", 4.2, 20.0, True), ("SSX7", "X", 1.7, 16.7, True),),
    "SSX7": (("SSX4", "X", 1.7, 25.0, True), ("SSX4B", "X", 1.7, 25.0, True), ("SSX5", "X", 0.8, 17.5, True),),
    "ST13": (("ST13P4", "13", 0, 19.2, False),),
    "STAT5A": (("STAT5B", "17", 7.5, 17.5, True),),
    "STAT5B": (("STAT5A", "17", 1.7, 11.7, True),),
    "STRC": (("STRCP1", "15", 70.0, 62.5, False),),
    "SULT1A1": (("SULT1A2", "16", 1.7, 42.5, True), ("SULT1A3", "16", 0.8, 34.2, True), ("SULT1A4", "16", 0.8, 34.2, True),),
    "SULT1A2": (("SULT1A1", "16", 9.2, 51.7, True), ("SULT1A3", "16", 0.8, 37.5, True), ("SULT1A4", "16", 0.8, 37.5, True),),
    "SULT1A3": (("SULT1A4", "16", 81.7, 100.0, True), ("SULT1A2", "16", 2.5, 38.3, True), ("SULT1A1", "16", 4.2, 33.3, True),),
    "SULT1A4": (("SULT1A3", "16", 82.5, 100.0, True), ("SULT1A2", "16", 0.8, 38.3, True), ("SULT1A1", "16", 3.3, 33.3, True),),
    "SUPT20HL1": (("SUPT20HL2", "X", 26.7, 26.7, True),),
    "SUPT20HL2": (("SUPT20HL1", "X", 24.2, 24.2, True),),
    "SURF2": (("SURF1", "9", 16.7, 0, True),),
    "SUZ12": (("SUZ12P1", "17", 10.0, 0, False),),
    "TBL1Y": (("TBL1X", "X", 0, 12.5, True),),
    "TCEAL3": (("TCEAL5", "X", 13.3, 31.7, True), ("TCEAL6", "X", 4.2, 12.5, True),),
    "TCEAL5": (("TCEAL3", "X", 7.5, 40.0, True),),
    "TCP11X1": (("TCP11X2", "X", 93.3, 100.0, True),),
    "TCP11X2": (("TCP11X1", "X", 93.3, 100.0, True),),
    "TDGF1": (("TDGF1P3", "X", 0.8, 20.0, False),),
    "TGIF2LX": (("TGIF2LY", "Y", 53.3, 26.7, True),),
    "TGIF2LY": (("TGIF2LX", "X", 53.3, 26.7, True),),
    "TLR1": (("TLR6", "4", 4.2, 16.7, True),),
    "TNFSF13": (("TNFSF12", "17", 11.7, 0, True),),
    "TOP1": (("TOP1P1", "1", 0, 15.0, False),),
    "TP53TG3": (("TP53TG3B", "16", 100.0, 72.5, True), ("TP53TG3C", "16", 100.0, 72.5, True), ("TP53TG3E", "16", 100.0, 45.8, True),),
    "TP53TG3B": (("TP53TG3", "16", 100.0, 72.5, True), ("TP53TG3C", "16", 100.0, 72.5, True), ("TP53TG3E", "16", 100.0, 45.8, True),),
    "TP53TG3C": (("TP53TG3", "16", 100.0, 45.0, True), ("TP53TG3B", "16", 100.0, 45.0, True), ("TP53TG3E", "16", 100.0, 72.5, True),),
    "TP53TG3D": (("TP53TG3", "16", 28.3, 30.8, True), ("TP53TG3B", "16", 28.3, 30.8, True), ("TP53TG3C", "16", 28.3, 29.2, True),),
    "TP53TG3E": (("TP53TG3", "16", 100.0, 45.0, True), ("TP53TG3B", "16", 100.0, 45.0, True), ("TP53TG3C", "16", 100.0, 45.8, True),),
    "TP53TG3F": (("TP53TG3", "16", 100.0, 71.7, True), ("TP53TG3B", "16", 100.0, 71.7, True), ("TP53TG3C", "16", 100.0, 71.7, True),),
    "TPTE": (("TPTE2", "13", 10.8, 31.7, True),),
    "TPTE2": (("TPTE", "21", 5.8, 27.5, True),),
    "TRAPPC2B": (("TRAPPC2", "X", 0, 40.0, True),),
    "TSPY1": (("TSPY2", "Y", 14.9, 74.2, True),),
    "TSPY10": (("TSPY2", "Y", 18.2, 96.7, True),),
    "TSPY2": (("TSPY10", "Y", 75.0, 96.7, True), ("TSPY3", "Y", 75.0, 96.7, True), ("TSPY8", "Y", 74.2, 88.3, True),),
    "TSPY3": (("TSPY2", "Y", 18.2, 96.7, True),),
    "TSPY4": (("TSPY2", "Y", 15.9, 40.0, True),),
    "TSPY8": (("TSPY2", "Y", 17.5, 96.7, True),),
    "TUBA1A": (("TUBA1B", "12", 11.7, 36.7, True), ("TUBA1C", "12", 9.2, 32.5, True),),
    "TUBA1B": (("TUBA1A", "12", 15.8, 63.3, True), ("TUBA1C", "12", 15.0, 63.3, True),),
    "TUBA1C": (("TUBA1B", "12", 0, 28.3, True), ("TUBA1A", "12", 0, 25.8, True),),
    "TUBA3C": (("TUBA3D", "2", 1.7, 46.7, True), ("TUBA3E", "2", 1.7, 42.5, True),),
    "TUBA3D": (("TUBA3E", "2", 48.3, 76.7, True), ("TUBA3C", "13", 4.2, 48.3, True),),
    "TUBA3E": (("TUBA3D", "2", 49.2, 75.8, True), ("TUBA3C", "13", 5.0, 45.0, True),),
    "TUBB2A": (("TUBB2B", "6", 20.0, 52.5, True), ("TUBB4A", "19", 8.3, 20.0, True), ("TUBB3", "16", 3.3, 10.8, True),),
    "TUBB2B": (("TUBB2A", "6", 24.2, 47.5, True), ("TUBB4A", "19", 9.2, 18.3, True), ("TUBB3", "16", 5.0, 10.8, True),),
    "TUBB3": (("TUBB4A", "19", 1.7, 12.5, True), ("TUBB2A", "6", 0, 10.0, True), ("TUBB2B", "6", 0, 10.0, True),),
    "TUBB4A": (("TUBB2A", "6", 5.0, 12.5, True), ("TUBB2B", "6", 5.0, 12.5, True),),
    "TUBB4B": (("TUBB8", "10", 3.3, 10.0, True),),
    "TUBB8": (("TUBB8B", "18", 41.7, 69.2, True), ("TUBBP5", "9", 28.3, 39.2, False),),
    "TUBB8B": (("TUBB8", "10", 41.7, 69.2, True), ("TUBBP5", "9", 30.8, 45.0, False),),
    "TUBG1": (("TUBG2", "17", 4.2, 35.8, True),),
    "TUBG2": (("TUBG1", "17", 2.5, 32.5, True),),
    "TVP23B": (("TVP23C", "17", 40.8, 0, True),),
    "TVP23C": (("TVP23B", "17", 15.8, 0, True),),
    "TYW1": (("TYW1B", "7", 17.5, 50.8, True),),
    "TYW1B": (("TYW1", "7", 23.3, 59.2, True),),
    "UBB": (("UBBP4", "17", 10.0, 20.0, False),),
    "UGT2B10": (("UGT2B11", "4", 0, 25.8, True), ("UGT2B28", "4", 0.8, 18.3, True), ("UGT2B7", "4", 0, 15.8, True),),
    "UGT2B11": (("UGT2B28", "4", 13.3, 44.2, True), ("UGT2B10", "4", 4.2, 17.5, True),),
    "UGT2B15": (("UGT2B17", "4", 15.0, 47.5, True),),
    "UGT2B17": (("UGT2B15", "4", 12.5, 44.2, True),),
    "UGT2B28": (("UGT2B11", "4", 15.0, 54.2, True), ("UGT2B10", "4", 3.3, 15.0, True), ("UGT2B4", "4", 0, 10.8, True),),
    "UGT2B4": (("UGT2B11", "4", 0, 12.5, True), ("UGT2B28", "4", 0, 10.0, True),),
    "UGT2B7": (("UGT2B10", "4", 0.8, 15.8, True), ("UGT2B28", "4", 0.8, 12.5, True), ("UGT2B11", "4", 0, 12.5, True),),
    "UPK3BL1": (("UPK3BL2", "7", 79.2, 62.5, True),),
    "UPK3BL2": (("UPK3BL1", "7", 76.7, 57.5, True),),
    "UTP14A": (("UTP14C", "13", 0, 15.0, True),),
    "VCX": (("VCX3B", "X", 40.0, 82.5, True), ("VCX3A", "X", 36.7, 79.2, True), ("VCX2", "X", 26.7, 41.7, True),),
    "VCX2": (("VCX3A", "X", 58.3, 71.7, True), ("VCX3B", "X", 50.8, 63.3, True), ("VCX", "X", 48.3, 61.7, True),),
    "VCX3A": (("VCX3B", "X", 75.8, 76.7, True), ("VCX", "X", 48.3, 55.0, True), ("VCX2", "X", 44.2, 48.3, True),),
    "VCX3B": (("VCX3A", "X", 72.5, 67.5, True), ("VCX", "X", 48.3, 49.2, True), ("VCX2", "X", 31.7, 38.3, True),),
    "WASHC2A": (("WASHC2C", "10", 65.8, 57.5, True),),
    "WASHC2C": (("WASHC2A", "10", 61.7, 51.7, True),),
    "XAGE1A": (("XAGE1B", "X", 92.5, 0, True),),
    "XAGE1B": (("XAGE1A", "X", 94.2, 0, True),),
    "XCL1": (("XCL2", "1", 15.8, 30.8, True),),
    "XCL2": (("XCL1", "1", 15.0, 68.3, True),),
    "XKRY": (("XKRY2", "Y", 100.0, 100.0, True),),
    "XKRY2": (("XKRY", "Y", 100.0, 100.0, True),),
    "YBX3": (("YBX3P1", "16", 0, 13.3, False),),
    "ZC3H11A": (("ZC3H11B", "1", 1.7, 42.5, True),),
    "ZC3H11B": (("ZC3H11A", "1", 19.2, 45.8, True),),
    # --- Ekzon duzeyinde olculen kopyalar (paralog_olc.py, GRCh38, 2026-10-29) ---
    # Bu genlerde uyari yoktu ama tasarimin ilk 3 ciftinin 3'u de kopyadan 0-2
    # uyumsuzlukla urun veriyordu. Kopyalarin cogu refGene'de yok (adsiz) ya da gen
    # govdesinin kucuk bir kismini kopyaladigi icin yuzde esiginin altinda kaliyordu.
    # 6. alan: kopyasi olculen ekzonlar (en az bunlar; olcum indel tolere etmez).
    # Adsiz kopyalar (refGene'de gen yok) konumla anilir; kromozom ayri alanda.
    "PTEN": (("PTENP1", "9", 0.0, 55.6, False, (2, 3, 4, 5, 8)),),
    "IKBKG": (("IKBKGP1", "X", 48.6, 80.0, False, (3, 4, 5, 6, 7, 8, 9, 10)),),
    "CHEK2": (("33,6 Mb", "16", 3.7, 20.0, False, (12, 14, 15)),
              ("32,4 Mb", "16", 2.8, 13.3, False, (14, 15)),),
    "NF1": (("18,7 Mb", "14", 0.0, 6.9, False, (16, 22, 24, 36)),
            ("131,2 Mb", "2", 0.0, 6.9, False, (16, 22, 24, 36)),
            ("15,6 Mb", "22", 0.0, 5.2, False, (22, 24, 36)),
            ("14,0 Mb", "21", 0.2, 3.4, False, (11, 15)),),
    "VWF": (("VWFP1", "22", 2.8, 9.6, False, (23, 24, 25, 26, 34)),),
    "HYDIN": (("HYDIN2", "1", 57.9, 86.0, False, (6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 43, 44, 45, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64, 65, 66, 67, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84)),),
}

# --- surum --------------------------------------------------------------
_ARALIK_ONBELLEK = {}


def gen_paraloglari(sembol):
    """Gen sembolunun tablodaki yakin-ozdes kopyalari (bos liste = bilinen yok)."""
    if not sembol:
        return []
    kayitlar = PARALOGLAR.get(str(sembol).strip().upper(), ())
    # 6. alan (istege bagli): kopyasi olan ekzon numaralari - paralog_olc.py uretir
    return [{"ad": x[0], "chrom": x[1], "dna": x[2], "ekzon": x[3], "kodlayan": x[4],
             "ekzonlar": tuple(x[5]) if len(x) > 5 else ()}
            for x in kayitlar]


def _araliklar(assembly):
    """Yalnizca TABLODAKI genlerin refGene sinirlari: {kromozom: [(bas, son, sembol)]}.
    Tablo kucuk oldugu icin (birkac yuz gen) konumdan gen bulmak ucuz kalir.
    Transkript tablosu yoksa None doner - o zaman konumdan gen bulunamaz."""
    if assembly in _ARALIK_ONBELLEK:
        return _ARALIK_ONBELLEK[assembly]
    if not PARALOGLAR:
        return {}            # tablo bossa transkript indeksini bosuna yukleme
    try:
        import transcripts as tr
        idx = tr._load_index(assembly)
    except Exception:
        return None
    out = {}
    for sembol in PARALOGLAR:
        for r in idx["by_gene"].get(sembol, []):
            c = str(r["chrom"]).replace("chr", "")
            out.setdefault(c, []).append((r["tx_start"], r["tx_end"], sembol))
    _ARALIK_ONBELLEK[assembly] = out
    return out


def konum_genleri(assembly, chrom, start, end=None):
    """Verilen aralikla kesisen, TABLODAKI gen sembolleri (genellikle 0 ya da 1)."""
    ar = _araliklar(assembly)
    if not ar:
        return []
    son = start if end is None else end
    c = str(chrom).replace("chr", "")
    bulunan = []
    for a, b, sembol in ar.get(c, []):
        if a <= son and start <= b and sembol not in bulunan:
            bulunan.append(sembol)
    return bulunan


def _yuzde(x):
    """67.5 -> '67,5' ; 40.0 -> '40'  (Turkce ondalik ayraci virgul)."""
    s = f"{float(x or 0):g}"
    return s.replace(".", ",")


def _uygun(k, mod):
    """Bu kayit bu modda uyari verdirir mi?"""
    dna, ekz = k.get("dna") or 0, k.get("ekzon") or 0
    if k.get("ekzonlar"):
        # Kismi psodogen: govde yuzdesi kucuk ama bu ekzonlardaki primer kopyadan
        # birebir urun verir (VWFP1 = VWF ekzon 23-34). Yuzde esigi burada yanilir.
        return True
    if mod == "cdna":
        return ekz >= CDNA_ESIK
    return dna >= DNA_ESIK or ekz >= EKZON_YOGUN_ESIK


def _tur(k):
    """Kopya ayri bir gen mi, psodogen mi? (refGene'de NM_ varsa gen)"""
    return t("paralog gen", "paralogous gene") if k.get("kodlayan") else t("psödogen",
                                                                          "pseudogene")


def _ekzon_araligi(nolar):
    """(3, 4, 5, 9) -> '3–5, 9'"""
    nolar = sorted(set(nolar))
    parca, bas = [], None
    for i, n in enumerate(nolar):
        if bas is None:
            bas = n
        if i + 1 == len(nolar) or nolar[i + 1] != n + 1:
            parca.append(str(bas) if bas == n else f"{bas}–{n}")
            bas = None
    return ", ".join(parca)


def _kapanis(rozet):
    """Uyarinin son cumlesi (tr, en). rozet=True: DNA tasarimi - arayuz ciftleri arka
    planda genomda tarayip kartlara rozet ekler (v0.8.9). Diger modlarda (RNA/cDNA,
    ekzon atlama, kirilma noktasi) otomatik tarama yok, yalnizca dugme."""
    if rozet:
        return ("Hangi çiftin kopyadan da ürün verdiğini özgüllük taraması söyler: "
                "kartlardaki otomatik rozetlere bakın (kapalıysa \"Özgüllüğü kontrol et\" "
                "düğmesine basın).",
                "The specificity scan shows which pairs also amplify the copy: check the "
                "automatic badges on the cards (if switched off, press \"Check specificity\").")
    return ("Tasarım bunu kendiliğinden kontrol etmez; her çift için \"Özgüllüğü kontrol "
            "et\" düğmesine basın.",
            "The design does not check this on its own; press \"Check specificity\" for "
            "each pair.")


def _ekzon_notu(gen, kayitlar, kapanis_tr, kapanis_en):
    liste_tr = "; ".join(f"ekzon {_ekzon_araligi(k['ekzonlar'])} → {k['ad']} "
                         f"(chr{k['chrom']}, {_tur(k)})" for k in kayitlar)
    liste_en = "; ".join(f"exon {_ekzon_araligi(k['ekzonlar'])} → {k['ad']} "
                         f"(chr{k['chrom']}, {_tur(k)})" for k in kayitlar)
    # "Diger ekzonlar etkilenmez" DENMEZ: olcum en az bu ekzonlari gosterir (indel
    # tolere etmez); pilotta VWF ekzon 28 ve NF1 ekzon 10 ciftleri de kopyadan urun verdi.
    return t(
        f"{gen} geninin bazı ekzonlarının genomda yakın-özdeş kopyası var: {liste_tr}. "
        "Bu ekzonlara konan primerler kopyadan da ürün verebilir — iki lokus birlikte "
        "çoğalırsa hastanın varyantı seyrelir ya da kopyanınki hastaya yazılır. Liste en "
        f"az bu ekzonları gösterir; komşu ekzonlar da etkilenebilir. {kapanis_tr}",
        f"Some exons of {gen} have a near-identical copy in the genome: {liste_en}. "
        "Primers placed on these exons may also amplify the copy — if both loci amplify, "
        "the patient's variant is diluted or the copy's sequence is attributed to the "
        "patient. The list shows at least these exons; neighbouring exons may also be "
        f"affected. {kapanis_en}")


def not_metni(gen, kayitlar, mod="dna", rozet=False):
    """mod: 'dna' (genomik tasarim) | 'cdna' (RNA/cDNA). rozet: arayuz bu sonucun
    ciftlerini otomatik tarar mi (yalnizca DNA tasarimi). Uyari gerekmiyorsa None."""
    kayitlar = [k for k in (kayitlar or []) if _uygun(k, mod)]
    if not kayitlar:
        return None
    ekzonlu = sorted((k for k in kayitlar if k.get("ekzonlar")),
                     key=lambda k: -len(k["ekzonlar"]))
    if ekzonlu:
        return _ekzon_notu(gen, ekzonlu[:4], *_kapanis(rozet))
    anahtar = "ekzon" if mod == "cdna" else "dna"
    kayitlar = sorted(kayitlar, key=lambda k: -(k.get(anahtar) or 0))[:3]
    oran = kayitlar[0].get(anahtar) or 0
    diger = kayitlar[0].get("ekzon" if mod == "dna" else "dna") or 0
    adlar = ", ".join(f"{k['ad']} (chr{k['chrom']}, {_tur(k)})" for k in kayitlar)
    # "%67,5 kadarı" kalibi bilerek: yuzde degerine gore degisen Turkce iyelik eki
    # ('-i / -ı / -u') gerektirmez.
    bas_tr = (f"{gen} geninin genomda yakın-özdeş "
              + ("kopyaları var" if len(kayitlar) > 1 else "bir kopyası var")
              + f": {adlar}.")
    bas_en = (f"{gen} has "
              + ("near-identical copies" if len(kayitlar) > 1 else "a near-identical copy")
              + f" in the genome: {adlar}.")
    kapanis_tr, kapanis_en = _kapanis(rozet)

    if mod == "dna" and oran < DNA_ESIK <= diger:
        # Benzerlik ekzonlarda yogun: ya islenmis psodogen (intronsuz) ya da intronlari
        # ayrismis bir paralog gen (ADH1A/B/C, MYH6/MYH7). Ikisini de kapsayan ifade.
        return t(
            f"{bas_tr} Benzerlik ekzonlarda yoğun, intronlar ayrışmış: gen gövdesinin "
            f"yalnızca %{_yuzde(oran)} kadarı benzer, ekzon dizisinin %{_yuzde(diger)} "
            f"kadarı en az %{KIMLIK_ESIGI} benzerlikte. Ekzon üzerine oturan primerler "
            f"kopyadan da ürün verebilir; intron içindekiler etkilenmez. {kapanis_tr}",
            f"{bas_en} The similarity is concentrated in the exons while the introns have "
            f"diverged: only {oran:g}% of the gene body is similar, but {diger:g}% of the "
            f"exon sequence is at least {KIMLIK_ESIGI}% identical. Primers sitting on an "
            f"exon may also amplify the copy; those inside introns are unaffected. "
            f"{kapanis_en}")

    if mod == "cdna":
        nerede_tr = f"Ekzon dizisinin %{_yuzde(oran)} kadarı"
        nerede_en = f"{oran:g}% of the exon sequence is"
    else:
        nerede_tr = f"Gen gövdesinin (intronlar dahil) %{_yuzde(oran)} kadarı"
        nerede_en = f"{oran:g}% of the gene body (introns included) is"

    hangi_tr = "en benzer kopyada" if len(kayitlar) > 1 else "bu kopyada"
    return t(
        f"{bas_tr} {nerede_tr} {hangi_tr} en az %{KIMLIK_ESIGI} benzerlikte. Buraya konan "
        "primerler kopyadan da ürün verebilir — iki lokus birlikte çoğalırsa hastanın "
        f"varyantı seyrelir ya da kopyanınki hastaya yazılır. {kapanis_tr}",
        f"{bas_en} {nerede_en} at least {KIMLIK_ESIGI}% identical to that copy. Primers "
        "placed here may also amplify the copy — if both loci amplify, the patient's variant "
        "is diluted or the copy's sequence is attributed to the patient. "
        f"{kapanis_en}")


def notu(assembly, gen=None, chrom=None, start=None, end=None, mod="dna", rozet=False):
    """Kolay giris: gen adi biliniyorsa ondan, yoksa koordinattan bul; not ya da None."""
    semboller = [gen.strip().upper()] if gen else []
    # Gen adi verilse bile tabloda yoksa koordinata da bakilir: kullanici eski/alternatif
    # bir sembol yazmis ya da komsu bir gen icinde olabilir.
    if chrom and start:
        semboller += [s for s in konum_genleri(assembly, chrom, int(start), int(end or start))
                      if s not in semboller]
    for s in semboller:
        kayitlar = gen_paraloglari(s)
        if kayitlar:
            return not_metni(s, kayitlar, mod, rozet)
    return None
