# -*- coding: utf-8 -*-

"""
  Export Kanaldaten nach HYSTEM-EXTRAN
  ====================================

  Transfer von Kanaldaten aus einer QKan-Datenbank nach HYSTEM EXTRAN 7.6

  | Dateiname            : k_qkhe.py
  | Date                 : Februar 2017
  | Copyright            : (C) 2016 by Joerg Hoettges
  | Email                : hoettges@fh-aachen.de
  | git sha              : $Format:%H$

  This program is free software; you can redistribute it and/or modify  
  it under the terms of the GNU General Public License as published by  
  the Free Software Foundation; either version 2 of the License, or     
  (at your option) any later version.                                  

"""

import os, shutil

from QKan_Database.fbfunc import FBConnection
from QKan_Database.dbfunc import DBConnection

# import pyspatialite.dbapi2 as splite
# import site, shutil
# import json
import time
import math
from qgis.core import QgsMessageLog
# from qgis.core import QgsGeometry, QgsFeature
# import qgis.utils
from qgis.gui import QgsMessageBar
from qgis.utils import iface
import logging

logger = logging.getLogger('QKan')

# Fortschritts- und Fehlermeldungen

def fortschritt(text,prozent=0.):
    logger.debug(u'{:s} ({:.0f}%)'.format(text,prozent*100.))
    QgsMessageLog.logMessage(u'{:s} ({:.0f}%)'.format(text,prozent*100.), 'Export: ', QgsMessageLog.INFO)

def fehlermeldung(title, text, dauer = 0):
    logger.debug(u'{:s} {:s}'.format(title,text))
    QgsMessageLog.logMessage(u'{:s} {:s}'.format(title, text), level=QgsMessageLog.CRITICAL)
    iface.messageBar().pushMessage(title, text, level=QgsMessageBar.CRITICAL, duration=dauer)

def exportKanaldaten(iface, database_HE, dbtemplate_HE, database_QKan, auswahl_Teilgebiete = "",
                     check_tabinit = False, check_difftezg = True):
    '''Export der Kanaldaten aus einer QKan-SpatiaLite-Datenbank und Schreiben in eine HE-Firebird-Datenbank.

    :database_HE:   Datenbankobjekt, das die Verknüpfung zur HE-Firebird-Datenbank verwaltet
    :type database_HE: string

    :dbtemplate_HE: Vorlage für die zu erstellende Firebird-Datenbank
    :type dbtemplate_HE: string

    :database_QKan: Datenbankobjekt, das die Verknüpfung zur QKan-SpatiaLite-Datenbank verwaltet.
    :type database_QKan: string

    :dbtyp:         Typ der Datenbank (SpatiaLite, PostGIS)
    :type dbtyp:    String

    :returns: void
    '''

    logger.debug('Status tabinit: {}'.format(str(check_tabinit)))
    logger.debug('Status difftezg: {}'.format(str(check_difftezg)))

    # ITWH-Datenbank aus gewählter Vorlage kopieren
    if os.path.exists(database_HE):
        try:
            os.remove(database_HE)
        except BaseException as err:
            fehlermeldung(u"Die HE-Datenbank ist schon vorhanden und kann nicht ersetzt werden: ",
                err)
            return False
    try:
        shutil.copyfile(dbtemplate_HE, database_HE)
    except BaseException as err:
        fehlermeldung(u"Kopieren der Vorlage HE-Datenbank fehlgeschlagen: ",
            err)
        return False
    fortschritt(u"Firebird-Datenbank aus Vorlage kopiert...",0.01)

    # Verbindung zur Hystem-Extran-Datenbank

    dbHE = FBConnection(database_HE)        # Datenbankobjekt der HE-Datenbank zum Schreiben

    if dbHE is None:
        fehlermeldung(u"(1) Fehler",
           'ITWH-Datenbank {:s} wurde nicht gefunden!\nAbbruch!'.format(database_HE))
        return None

    # Verbindung zur QKan-Datenbank

    dbQK = DBConnection(database_QKan)      # Datenbankobjekt der QKan-Datenbank zum Lesenen

    if dbQK is None:
        fehlermeldung(u"(2) Fehler",
           'QKan-Datenbank {:s} wurde nicht gefunden!\nAbbruch!'.format(database_QKan))
        return None

    # --------------------------------------------------------------------------------------------------
    # Kontrolle der vorhandenen Profilquerschnitte. 

    fortschritt('Pruefung der Profiltypen...', 0.02)

    # --------------------------------------------------------------------------------------------------
    # Zur Abschaetzung der voraussichtlichen Laufzeit

    dbQK.sql("SELECT count(*) As n FROM schaechte")
    anzdata = float(dbQK.fetchone()[0])
    fortschritt(u"Anzahl Schächte: {}".format(anzdata))
    # print('anz: {:}'.format(anzdata))
    dbQK.sql("SELECT count(*) As n FROM haltungen")
    anzdata += float(dbQK.fetchone()[0])
    fortschritt(u"Anzahl Haltungen: {}".format(anzdata))
    # print('anz: {:}'.format(anzdata))
    dbQK.sql("SELECT count(*) As n FROM flaechen")
    anzdata += float(dbQK.fetchone()[0])*2
    fortschritt(u"Anzahl Flächen: {}".format(anzdata))
    # print('anz: {:}'.format(anzdata))

    # --------------------------------------------------------------------------------------------
    # Besonderes Gimmick des ITWH-Programmiers: Die IDs der Tabellen muessen sequentiell
    # vergeben werden!!! Ein Grund ist, dass (u.a.?) die Tabelle "tabelleninhalte" mit verschiedenen
    # Tabellen verknuepft ist und dieser ID eindeutig sein muss.

    dbHE.sql("SELECT NEXTID FROM ITWH$PROGINFO")
    nextid = int(dbHE.fetchone()[0])

    # --------------------------------------------------------------------------------------------
    # Export der Schaechte

    if check_tabinit:
        dbHE.sql("DELETE FROM SCHACHT")

    # Nur Daten fuer ausgewaehlte Teilgebiete
    if auswahl_Teilgebiete != "":
        auswahl = " and schaechte.teilgebiet in ({:})".format(auswahl_Teilgebiete)
    else:
        auswahl = ""

    sql = u"""
        SELECT 
            schaechte.schnam AS schnam, 
            schaechte.deckelhoehe AS deckelhoehe, 
            schaechte.sohlhoehe AS sohlhoehe, 
            schaechte.strasse AS strasse, 
            schaechte.xsch AS xsch, 
            schaechte.ysch AS ysch
        FROM schaechte
        WHERE schaechte.schachttyp = 'Schacht'{}
        """.format(auswahl)
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(21) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False


    nr0 = nextid

    fortschritt('Export Schaechte Teil 1...', 0.1)
    createdat = time.strftime('%d.%m.%Y %H:%M:%S',time.localtime())
    for attr in dbQK.fetchall():

        # In allen Feldern None durch NULL ersetzen
        (schnam, deckelhoehe_t, sohlhoehe_t, strasse, xsch_t, ysch_t) = \
            ('NULL' if el is None else el for el in attr)

        # Formatierung der Zahlen
        (deckelhoehe, sohlhoehe, xsch, ysch) = \
            ('NULL' if tt == 'NULL' else '{:.3f}'.format(float(tt)) \
                for tt in (deckelhoehe_t, sohlhoehe_t, xsch_t, ysch_t))

        # Einfuegen in die Datenbank

        sql = u"""
            INSERT INTO SCHACHT
            ( DECKELHOEHE, KANALART, DRUCKDICHTERDECKEL, SOHLHOEHE, XKOORDINATE, YKOORDINATE,
            KONSTANTERZUFLUSS, GELAENDEHOEHE, ART, ANZAHLKANTEN, SCHEITELHOEHE, 
            PLANUNGSSTATUS, NAME, LASTMODIFIED, ID, DURCHMESSER) VALUES
            ({deckelhoehe}, {kanalart}, {druckdichterdeckel}, {sohlhoehe}, {xkoordinate},
             {ykoordinate}, {konstanterzufluss}, {gelaendehoehe}, {art}, {anzahlkanten},
             {scheitelhoehe}, '{planungsstatus}', '{name}', '{lastmodified}', {id}, {durchmesser});
        """.format(deckelhoehe=deckelhoehe, kanalart='0', druckdichterdeckel='0',
                   sohlhoehe=sohlhoehe, xkoordinate=xsch, ykoordinate=ysch,
                   konstanterzufluss='0', gelaendehoehe=deckelhoehe, art='1', anzahlkanten='0',
                   scheitelhoehe='0', planungsstatus='0', name=schnam, lastmodified=createdat,
                   id=nextid, durchmesser='1000.')
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(3) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False

        nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt('{} Schaechte eingefuegt'.format(nextid-nr0), 0.30)

    # --------------------------------------------------------------------------------------------
    # Export der Speicherbauwerke

    if check_tabinit:
        dbHE.sql("DELETE FROM SPEICHERSCHACHT")

    # Nur Daten fuer ausgewaehlte Teilgebiete
    if auswahl_Teilgebiete != "":
        auswahl = " and schaechte.teilgebiet in ({:})".format(auswahl_Teilgebiete)
    else:
        auswahl = ""

    sql = u"""
        SELECT 
            schaechte.schnam AS schnam, 
            schaechte.deckelhoehe AS deckelhoehe_t, 
            schaechte.sohlhoehe AS sohlhoehe_t, 
            schaechte.strasse AS strasse, 
            schaechte.xsch AS xsch_t, 
            schaechte.ysch AS ysch_t, 
            kommentar AS kommentar
        FROM schaechte
        WHERE schaechte.schachttyp = 'Speicher'{}
        """.format(auswahl)
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(22) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False


    nr0 = nextid

    createdat = time.strftime('%d.%m.%Y %H:%M:%S',time.localtime())
    for attr in dbQK.fetchall():
        fortschritt('Export Speichersschaechte...', 0.15)

        # In allen Feldern None durch NULL ersetzen
        (schnam, deckelhoehe_t, sohlhoehe_t, strasse, xsch_t, ysch_t, kommentar) = \
            ('NULL' if el is None else el for el in attr)

        # Formatierung der Zahlen
        (deckelhoehe, sohlhoehe, xsch, ysch) = \
            ('NULL' if tt == 'NULL' else '{:.3f}'.format(float(tt)) \
                for tt in (deckelhoehe_t, sohlhoehe_t, xsch_t, ysch_t))

        # Einfuegen in die Datenbank

        sql = u"""
            INSERT INTO SPEICHERSCHACHT
            ( ID, TYP, SOHLHOEHE, 
              XKOORDINATE, YKOORDINATE, 
              GELAENDEHOEHE, ART, ANZAHLKANTEN, 
              SCHEITELHOEHE, HOEHEVOLLFUELLUNG,
              KONSTANTERZUFLUSS, ABSETZWIRKUNG, PLANUNGSSTATUS,
              NAME, LASTMODIFIED, KOMMENTAR) VALUES
            ( {id}, {typ}, {sohlhoehe}, 
              {xkoordinate}, {ykoordinate}, 
              {gelaendehoehe}, {art}, {anzahlkanten},
              {scheitelhoehe}, {hoehevollfuellung},
              '{konstanterzufluss}', '{absetzwirkung}', '{planungsstatus}',
              '{name}', '{lastmodified}', '{kommentar}');
        """.format(id=nextid, typ='1', sohlhoehe=sohlhoehe, 
                   xkoordinate=xsch, ykoordinate=ysch,
                   gelaendehoehe=deckelhoehe, art='1', anzahlkanten='0',
                   scheitelhoehe=deckelhoehe, hoehevollfuellung=deckelhoehe,
                   konstanterzufluss = '0', absetzwirkung='0', planungsstatus='0',
                   name=schnam, lastmodified=createdat, kommentar = kommentar, 
                   durchmesser='1000.')
        # print(sql)
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(4) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False

        nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt('{} Speicher eingefuegt'.format(nextid-nr0), 0.40)

    # --------------------------------------------------------------------------------------------
    # Export der Auslaesse

    if check_tabinit:
        dbHE.sql("DELETE FROM AUSLASS")

    # Nur Daten fuer ausgewaehlte Teilgebiete
    if auswahl_Teilgebiete != "":
        auswahl = " and schaechte.teilgebiet in ({:})".format(auswahl_Teilgebiete)
    else:
        auswahl = ""

    sql = u"""
        SELECT
            schaechte.schnam AS schnam,
            schaechte.deckelhoehe AS deckelhoehe_t,
            schaechte.sohlhoehe AS sohlhoehe_t,
            schaechte.xsch AS xsch_t,
            schaechte.ysch AS ysch_t,
            kommentar AS kommentar
        FROM schaechte
        WHERE schaechte.schachttyp = 'Auslass'{}
        """.format(auswahl)
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(22) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False


    nr0 = nextid

    createdat = time.strftime('%d.%m.%Y %H:%M:%S',time.localtime())

    fortschritt(u'Export Auslässe...', 0.15)

    for attr in dbQK.fetchall():

        # In allen Feldern None durch NULL ersetzen
        (schnam, deckelhoehe_t, sohlhoehe_t, xsch_t, ysch_t, kommentar) = \
            ('NULL' if el is None else el for el in attr)

        # Formatierung der Zahlen
        (deckelhoehe, sohlhoehe, xsch, ysch) = \
            ('NULL' if tt == 'NULL' else '{:.3f}'.format(float(tt)) \
                for tt in (deckelhoehe_t, sohlhoehe_t, xsch_t, ysch_t))

        # Einfuegen in die Datenbank

        sql = u"""
            INSERT INTO AUSLASS
            ( ID, TYP, RUECKSCHLAGKLAPPE, SOHLHOEHE,
              XKOORDINATE, YKOORDINATE,
              GELAENDEHOEHE, ART, ANZAHLKANTEN,
              SCHEITELHOEHE, KONSTANTERZUFLUSS, PLANUNGSSTATUS,
              NAME, LASTMODIFIED, KOMMENTAR) VALUES
            ( {id}, {typ}, {rueckschlagklappe}, {sohlhoehe},
              {xkoordinate}, {ykoordinate},
              {gelaendehoehe}, {art}, {anzahlkanten},
              {scheitelhoehe}, {konstanterzufluss}, '{planungsstatus}',
              '{name}', '{lastmodified}', '{kommentar}');
        """.format(id=nextid, typ='1', rueckschlagklappe=0, sohlhoehe=sohlhoehe,
                   xkoordinate=xsch, ykoordinate=ysch,
                   gelaendehoehe=deckelhoehe, art='3', anzahlkanten='0',
                   scheitelhoehe=deckelhoehe, konstanterzufluss=0, planungsstatus='0',
                   name=schnam, lastmodified=createdat, kommentar = kommentar,
                   durchmesser='1000.')
        # print(sql)
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(31) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False

        nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt(u'{} Auslässe eingefuegt'.format(nextid-nr0), 0.40)

    # --------------------------------------------------------------------------------------------
    # Export der Haltungen
    #
    # Erläuterung zum Feld "GESAMTFLAECHE":
    # Die Haltungsfläche (area(tezg.geom)) wird in das Feld "GESAMTFLAECHE" eingetragen und erscheint damit
    # in HYSTEM-EXTRAN in der Karteikarte "Haltungen > Trockenwetter". Solange dort kein
    # Siedlungstyp zugeordnet ist, wird diese Fläche nicht wirksam und dient nur der Information!

    if check_tabinit:
        dbHE.sql("DELETE FROM ROHR")

    # Nur Daten fuer ausgewaehlte Teilgebiete
    if auswahl_Teilgebiete != "":
        auswahl = " and haltungen.teilgebiet in ({:})".format(auswahl_Teilgebiete)
    else:
        auswahl = ""

    sql = u"""
      SELECT 
          haltungen.haltnam AS haltnam, haltungen.schoben AS schoben, haltungen.schunten AS schunten,
          coalesce(haltungen.laenge,
            sqrt((n2.xsch-n1.xsch)*(n2.xsch-n1.xsch)+(n2.ysch-n1.ysch)*(n2.ysch-n1.ysch))) AS laenge_t,
          coalesce(haltungen.sohleoben,n1.sohlhoehe) AS sohleoben_t,
          coalesce(haltungen.sohleunten,n2.sohlhoehe) AS sohleunten_t,
          haltungen.profilnam AS profilnam, profile.he_nr AS he_nr, haltungen.hoehe AS hoehe_t, haltungen.breite AS breite_t,
          entwaesserungsarten.he_nr AS entw_nr,
          haltungen.rohrtyp AS rohrtyp, haltungen.ks AS rauheit_t,
          haltungen.teilgebiet AS teilgebiet, haltungen.createdat AS createdat
        FROM
          (haltungen JOIN schaechte AS n1 ON haltungen.schoben = n1.schnam)
          JOIN schaechte AS n2 ON haltungen.schunten = n2.schnam
          LEFT JOIN profile ON haltungen.profilnam = profile.profilnam
          LEFT JOIN entwaesserungsarten ON haltungen.entwart = entwaesserungsarten.kuerzel
          LEFT JOIN tezg ON haltungen.haltnam = tezg.haltnam
          LEFT JOIN simulationsstatus AS st ON haltungen.simstatus = st.bezeichnung
          WHERE (st.he_nr = '0' or st.he_nr IS NULL){:}
    """.format(auswahl)
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(5) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False

    fortschritt('Export Haltungen...', 0.35)

    nr0 = nextid

    for attr in dbQK.fetchall():

        # In allen Feldern None durch NULL ersetzen
        (haltnam, schoben, schunten, laenge_t, sohleoben_t, sohleunten_t, profilnam,
         he_nr, hoehe_t, breite_t, entw_nr, rohrtyp, rauheit_t, teilgebiet, createdat) = \
         ('NULL' if el is None else el for el in attr)

        createdat = createdat[:19]
        # Datenkorrekturen
        (laenge, sohleoben, sohleunten, hoehe, breite) = \
           ('NULL' if tt == 'NULL' else '{:.4f}'.format(float(tt)) \
                for tt in (laenge_t, sohleoben_t, sohleunten_t, hoehe_t, breite_t))

        if rauheit_t is None:
            rauheit = '1.5'
        else:
            rauheit = '{:.3f}'.format(float(rauheit_t))

            h_profil = he_nr
        if h_profil == '68':
            h_sonderprofil = profilnam
        else:
            h_sonderprofil = ''

        # Einfuegen in die Datenbank
        # Profile < 0 werden nicht uebertragen
        if int(h_profil) > 0:
            sql = u"""
              INSERT INTO ROHR 
              ( NAME, SCHACHTOBEN, SCHACHTUNTEN, LAENGE, SOHLHOEHEOBEN,
                SOHLHOEHEUNTEN, PROFILTYP, SONDERPROFILBEZEICHNUNG, GEOMETRIE1,
                GEOMETRIE2, KANALART, RAUIGKEITSBEIWERT, ANZAHL, TEILEINZUGSGEBIET,
                RUECKSCHLAGKLAPPE, KONSTANTERZUFLUSS, EINZUGSGEBIET, KONSTANTERZUFLUSSTEZG,
                RAUIGKEITSANSATZ, GEFAELLE, GESAMTFLAECHE, ABFLUSSART,
                INDIVIDUALKONZEPT, HYDRAULISCHERRADIUS, RAUHIGKEITANZEIGE, PLANUNGSSTATUS,
                LASTMODIFIED, MATERIALART, EREIGNISBILANZIERUNG, EREIGNISGRENZWERTENDE,
                EREIGNISGRENZWERTANFANG, EREIGNISTRENNDAUER, EREIGNISINDIVIDUELL, ID)
              VALUES
                ('{name}', '{schachtoben}', '{schachtunten}', {laenge}, {sohlhoeheoben},
                {sohlhoeheunten}, '{profiltyp}', '{sonderprofilbezeichnung}', {geometrie1},
                {geometrie2}, '{kanalart}', {rauigkeitsbeiwert}, {anzahl}, '{teileinzugsgebiet}',
                {rueckschlagklappe}, {konstanterzufluss}, {einzugsgebiet}, {konstanterzuflusstezg},
                {rauigkeitsansatz}, {gefaelle}, {gesamtflaeche}, {abflussart},
                {individualkonzept}, {hydraulischerradius}, {rauhigkeitanzeige}, {planungsstatus},
                '{lastmodified}', {materialart}, {ereignisbilanzierung}, {ereignisgrenzwertende},
                {ereignisgrenzwertanfang}, {ereignistrenndauer}, {ereignisindividuell}, {id})
              """.format(name=haltnam, schachtoben=schoben, schachtunten=schunten,
                           laenge=laenge, sohlhoeheoben=sohleoben,
                         sohlhoeheunten=sohleunten, profiltyp=h_profil,
                           sonderprofilbezeichnung=h_sonderprofil, geometrie1=hoehe,
                         geometrie2=breite, kanalart=entw_nr,
                           rauigkeitsbeiwert=1.5, anzahl=1, teileinzugsgebiet=teilgebiet,
                         rueckschlagklappe=0, konstanterzufluss=0,
                           einzugsgebiet=0, konstanterzuflusstezg = 0,
                         rauigkeitsansatz=1, gefaelle=0,
                           gesamtflaeche=0, abflussart=0,
                         individualkonzept=0, hydraulischerradius=0,
                           rauhigkeitanzeige=1.5, planungsstatus=0,
                         lastmodified=createdat, materialart=28,
                           ereignisbilanzierung=0, ereignisgrenzwertende=0,
                         ereignisgrenzwertanfang=0, ereignistrenndauer=0,
                           ereignisindividuell=0, id=nextid)
            try:
                dbHE.sql(sql)
            except:
                fehlermeldung(u"(6) SQL-Fehler in Firebird: \n", sql)
                del dbQK
                del dbHE
                return False

            nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt('{} Haltungen eingefuegt'.format(nextid-nr0), 0.60)

    # --------------------------------------------------------------------------------------------
    # Export der Bodenklassen: In QKan nicht enthalten, Vorlagedaten nur im Code enthalten

    if check_tabinit:
        dbHE.sql("DELETE FROM BODENKLASSE")

    createdat = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())

    daten = [[10, 9, 10, 144, 1.584, 100, 'VollDurchlaessig', createdat,  'Exportiert mit qkhe', nextid],
             [2.099,  0.16, 1.256, 227.9, 1.584, 12, 'Sand', createdat,  'Exportiert mit qkhe', nextid+1],
             [1.798,  0.101, 1.06, 143.9, 0.72, 18, 'SandigerLehm', createdat,  'Exportiert mit qkhe', nextid+2],
             [1.601, 0.081, 0.94, 100.2, 0.432, 23, 'LehmLoess', createdat,  'Exportiert mit qkhe', nextid+3],
             [1.9, 0.03, 1.087, 180, 0.144, 16, 'Ton', createdat,  'Exportiert mit qkhe', nextid+4]]

    nr0 = nextid

    for ds in daten:
        sql = u"""
          INSERT INTO BODENKLASSE (INFILTRATIONSRATEANFANG, INFILTRATIONSRATEENDE,
            INFILTRATIONSRATESTART, RUECKGANGSKONSTANTE, REGENERATIONSKONSTANTE,
            SAETTIGUNGSWASSERGEHALT, NAME, LASTMODIFIED, KOMMENTAR,  ID) VALUES 
                                  ({INFILTRATIONSRATEANFANG}, {INFILTRATIONSRATEENDE},
            {INFILTRATIONSRATESTART}, {RUECKGANGSKONSTANTE}, {REGENERATIONSKONSTANTE},
            {SAETTIGUNGSWASSERGEHALT}, '{NAME}', '{LASTMODIFIED}', '{KOMMENTAR}', {ID});
            """.format(INFILTRATIONSRATEANFANG=ds[0], INFILTRATIONSRATEENDE=ds[1],
            INFILTRATIONSRATESTART=ds[2], RUECKGANGSKONSTANTE=ds[3], REGENERATIONSKONSTANTE=ds[4],
            SAETTIGUNGSWASSERGEHALT=ds[5], NAME=ds[6], LASTMODIFIED=ds[7], KOMMENTAR=ds[8],  ID=ds[9])
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(7) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False

    nextid += 5
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt('{} Bodenklassen eingefuegt'.format(nextid-nr0), 0.62)

    # --------------------------------------------------------------------------------------------
    # Export der Abflussparameter: In QKan nicht enthalten, Vorlagedaten nur im Code enthalten

    if check_tabinit:
        dbHE.sql("DELETE FROM ABFLUSSPARAMETER")

    sql = u"""
        SELECT
            apnam,
            anfangsabflussbeiwert as anfangsabflussbeiwert_t,
            endabflussbeiwert as endabflussbeiwert_t,
            benetzungsverlust as benetzungsverlust_t,
            muldenverlust as muldenverlust_t,
            benetzung_startwert as benetzung_startwert_t,
            mulden_startwert as mulden_startwert_t,
            bodenklasse, kommentar, createdat
        FROM abflussparameter
        """.format(auswahl)
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(22) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False

    nr0 = nextid

    if createdat == 'NULL':
        createdat = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())

    fortschritt(u'Export Abflussparameter...', 70)

    for attr in dbQK.fetchall():

        # In allen Feldern None durch NULL ersetzen
        ( apnam, anfangsabflussbeiwert_t, endabflussbeiwert_t,
          benetzungsverlust_t, muldenverlust_t, benetzung_startwert_t,
          mulden_startwert_t, bodenklasse, kommentar, createdat) = \
        ('NULL' if el is None else el for el in attr)

        # Formatierung der Zahlen
        ( anfangsabflussbeiwert, endabflussbeiwert, benetzungsverlust,
          muldenverlust, benetzung_startwert, mulden_startwert) = \
            ('NULL' if tt == 'NULL' else '{:.2f}'.format(float(tt)) \
                for tt in (anfangsabflussbeiwert_t, endabflussbeiwert_t,
                           benetzungsverlust_t, muldenverlust_t, benetzung_startwert_t,
                           mulden_startwert_t))

        if bodenklasse == 'NULL':
            typ = 0                 # undurchlössig
        else:
            typ = 1                 # durchlässig

        sql = u"""
          INSERT INTO ABFLUSSPARAMETER
          ( NAME, ABFLUSSBEIWERTANFANG, ABFLUSSBEIWERTENDE, BENETZUNGSVERLUST,
            MULDENVERLUST, BENETZUNGSPEICHERSTART, MULDENAUFFUELLGRADSTART, SPEICHERKONSTANTEKONSTANT,
            SPEICHERKONSTANTEMIN, SPEICHERKONSTANTEMAX, SPEICHERKONSTANTEKONSTANT2,
            SPEICHERKONSTANTEMIN2, SPEICHERKONSTANTEMAX2,
            BODENKLASSE, CHARAKTERISTISCHEREGENSPENDE, CHARAKTERISTISCHEREGENSPENDE2,
            TYP, JAHRESGANGVERLUSTE, LASTMODIFIED, KOMMENTAR, ID)
          VALUES
          ( '{apnam}', {anfangsabflussbeiwert}, {endabflussbeiwert}, {benetzungsverlust},
            {muldenverlust}, {benetzung_startwert}, {mulden_startwert}, {speicherkonstantekonstant},
            {speicherkonstantemin}, {speicherkonstantemax}, {speicherkonstantekonstant2},
            {speicherkonstantemin2}, {speicherkonstantemax2},
            '{bodenklasse}', {charakteristischeregenspende}, {charakteristischeregenspende2},
            {typ}, {jahresgangverluste}, '{createdat}', '{kommentar}', {id})
        """.format(apnam=apnam, anfangsabflussbeiwert=anfangsabflussbeiwert,
                     endabflussbeiwert=endabflussbeiwert, benetzungsverlust=benetzungsverlust,
                   muldenverlust=muldenverlust, benetzung_startwert=benetzung_startwert,
                     mulden_startwert=mulden_startwert, speicherkonstantekonstant=1,
                   speicherkonstantemin=0, speicherkonstantemax=0, speicherkonstantekonstant2=1,
                   speicherkonstantemin2=0, speicherkonstantemax2=0,
                   bodenklasse=bodenklasse, charakteristischeregenspende=0, charakteristischeregenspende2=0,
                   typ=typ, jahresgangverluste=0, createdat=createdat, kommentar=kommentar, id=nextid)
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(8) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False
        nextid += 1

    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt('{} Abflussparameter eingefuegt'.format(nextid-nr0), 0.65)

    # ------------------------------------------------------------------------------------------------
    # Export der Regenschreiber: In QKan nicht enthalten, Vorlagedaten nur im Code enthalten
    #
    # Wenn in QKan keine Regenschreiber eingetragen sind, wird als Name "Regenschreiber1" angenommen.

    if check_tabinit:
        dbHE.sql("DELETE FROM REGENSCHREIBER")

    # # Pruefung, ob Regenschreiber fuer Export vorhanden
    # if auswahl_Teilgebiete != "":
    #     auswahl = " and flaechen.teilgebiet in ({:})".format(auswahl_Teilgebiete)
    # else:
    #     auswahl = ""
    #
    # sql = u"SELECT regenschreiber FROM flaechen GROUP BY regenschreiber{}".format(auswahl)

    # Regenschreiber berücksichtigen nicht ausgewählte Teilgebiete
    sql = u"SELECT regenschreiber FROM flaechen GROUP BY regenschreiber"
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(5) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False

    attr= dbQK.fetchall()
    if attr == [(None,)]:
        reglis = tuple(['Regenschreiber1'])
        logger.debug(u'In QKan war kein Regenschreiber vorhanden. "Regenschreiber1" ergänzt')
    else:
        reglis = tuple([str(el[0]) for el in attr])
        logger.debug(u'In QKan wurden folgende Regenschreiber referenziert: {}'.format(str(reglis)))

    logger.debug('Regenschreiber - reglis: {}'.format(str(reglis)))

    # Liste der fehlenden Regenschreiber in der Ziel- (*.idbf-) Datenbank
    # Hier muss eine Besonderheit von tuple berücksichtigt werden. Ein Tuple mit einem Element
    # endet mit ",)", z.B. (1,), während ohne oder bei mehr als einem Element alles wie üblich
    # ist: () oder (1,2,3,4)
    if len(reglis) == 1:
        sql = u"SELECT NAME FROM REGENSCHREIBER WHERE NAME NOT IN {})".format(str(reglis)[:-2])
    else:
        sql = u"SELECT NAME FROM REGENSCHREIBER WHERE NAME NOT IN {}".format(str(reglis))
    dbHE.sql(sql)

    attr = dbHE.fetchall()
    logger.debug('Regenschreiber - attr: {}'.format(str(attr)))

    nr0 = nextid

    regschnr = 1
    for regenschreiber in reglis:
        if regenschreiber not in attr:
            sql = u"""
              INSERT INTO REGENSCHREIBER
              ( NUMMER, STATION,
                XKOORDINATE, YKOORDINATE, ZKOORDINATE, NAME,
                FLAECHEGESAMT, FLAECHEDURCHLAESSIG, FLAECHEUNDURCHLAESSIG,
                ANZAHLHALTUNGEN, INTERNENUMMER,
                LASTMODIFIED, KOMMENTAR, ID) VALUES
                ({nummer}, '{station}',
                {xkoordinate}, {ykoordinate}, {zkoordinate}, '{name}',
                {flaechegesamt}, {flaechedurchlaessig}, {flaecheundurchlaessig},
                {anzahlhaltungen}, {internenummer},
                '{lastmodified}', '{kommentar}', {id})
              """.format(nummer=regschnr, station=10000 + regschnr,
                         xkoordinate=0, ykoordinate=0, zkoordinate=0, name=regenschreiber,
                         flaechegesamt=0, flaechedurchlaessig=0, flaecheundurchlaessig=0,
                         anzahlhaltungen=0, internenummer=0,
                         lastmodified=createdat, kommentar=u'Ergänzt durch QKan', id=nextid)

            try:
                dbHE.sql(sql)
            except:
                fehlermeldung(u"(17) SQL-Fehler in Firebird: \n", sql)
                del dbQK
                del dbHE
                return False

            logger.debug(u'In HE folgenden Regenschreiber ergänzt: {}'.format(sql))

            nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt('{} Regenschreiber eingefuegt'.format(nextid-nr0), 0.68)

        # sql = u"""
        # DELETE FROM REGENSCHREIBER;
    # """
    # dbHE.sql(sql)
    # sql = u"""
        # INSERT INTO REGENSCHREIBER (NUMMER, FLAECHEGESAMT, FLAECHEDURCHLAESSIG, FLAECHEUNDURCHLAESSIG, STATION, ANZAHLHALTUNGEN, INTERNENUMMER, XKOORDINATE, YKOORDINATE, ZKOORDINATE, NAME,          LASTMODIFIED,               KOMMENTAR,   ID)
        # VALUES
        # (     0,       24.5221,             16.9011,                 7.621,    1234,               0,              0,           0,           0,          0,    1, '13.01.2011 08:44:50',  'Exportiert mit qkhe', {:});
    # """.format(nextid)
    # dbHE.sql(sql)
    # nextid += 1
    # dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    # dbHE.commit()

    # ------------------------------------------------------------------------------------------------------
    # Export der Flaechendaten
    #
    # Die Daten werden in max. drei Teilen nach HYSTEM-EXTRAN exportiert:
    # 1. Befestigte Flächen
    # 2.1 Bei gesetzter Option check_difftezg:
    #     Fläche der tezg abzüglich der Summe aller (befestigter und unbefestigter!) Flächen
    # 2.2 Unbefestigte Flächen

    # Die Abflusseigenschaften werden über die Tabelle "abflussparameter" geregelt. Dort ist 
    # im attribut bodenklasse nur bei unbefestigten Flächen ein Eintrag. Dies ist das Kriterium
    # zur Unterscheidung

    # undurchlässigen Flächen -------------------------------------------------------------------------------

    if check_tabinit:
        dbHE.sql("DELETE FROM FLAECHE")

    # Nur Daten fuer ausgewaehlte Teilgebiete
    if auswahl_Teilgebiete != "":
        auswahl = " and flaechen.teilgebiet in ({:})".format(auswahl_Teilgebiete)
    else:
        auswahl = ""

    sql = u"""
      SELECT flaechen.flnam AS flnam, Coalesce(flaechen.haltnam,tezg.haltnam) AS haltnam, flaechen.neigkl AS neigkl,
        area(flaechen.geom) AS flaeche, flaechen.regenschreiber AS regenschreiber, 
        flaechen.abflussparameter AS abflussparameter, flaechen.createdat AS createdat, 
        flaechen.kommentar AS kommentar
      FROM flaechen
      LEFT JOIN abflussparameter
      ON flaechen.abflussparameter = abflussparameter.apnam
      LEFT JOIN tezg
      ON Within(Centroid(flaechen.geom),tezg.geom)
      WHERE abflussparameter.bodenklasse IS NULL and Coalesce(flaechen.haltnam,tezg.haltnam) IS NOT NULL{:}
    """.format(auswahl)
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(23) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False


    fortschritt('Export befestigte Flaechen...', 0.70)

    nr0 = nextid

    for attr in dbQK.fetchall():

        # In allen Feldern None durch NULL ersetzen
        (flnam, haltnam,  neigkl, flaeche, regenschreiber, abflussparameter, createdat, kommentar) = \
            ('NULL' if el is None else el for el in attr)

        # Datenkorrekturen

        # Formatierung der Zahlen
        if regenschreiber == 'NULL':
            regenschreiber = 'Regenschreiber1'

        if createdat == 'NULL':
            createdat = time.strftime('%d.%m.%Y %H:%M:%S',time.localtime())

        spkonst = math.sqrt(flaeche)*2.
        splaufz = math.sqrt(flaeche)*6.

        if kommentar is None or kommentar == '':
            kommentar = 'eingefuegt von k_qkhe'

        # befestigter Anteil
        sql = u"""
          INSERT INTO FLAECHE
          ( GROESSE, REGENSCHREIBER, HALTUNG, ANZAHLSPEICHER, 
            SPEICHERKONSTANTE, SCHWERPUNKTLAUFZEIT, BERECHNUNGSPEICHERKONSTANTE, TYP, 
            PARAMETERSATZ, NEIGUNGSKLASSE, NAME, LASTMODIFIED, 
            KOMMENTAR, ID, ZUORDNUNABHEZG)
          VALUES
          ( {flaeche:.4f}, '{regenschreiber}', '{haltnam}', {anzsp},
            {spkonst:.3f}, {splaufz:.2f}, {berspkonst}, {fltyp},
            '{abflussparameter}', {neigkl}, 'f_{flnam}', '{createdat}',
            '{kommentar}', {nextid}, {zuordnunabhezg});
          """.format(flaeche = flaeche, regenschreiber = regenschreiber, haltnam = haltnam, anzsp = 3, 
                     spkonst = spkonst, splaufz = splaufz, berspkonst = 2, fltyp = 0, 
                     abflussparameter = abflussparameter, neigkl = neigkl, flnam = flnam, createdat = createdat, 
                     kommentar = kommentar, nextid = nextid, zuordnunabhezg = 0)
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(9) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False

        nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt('{} Flaechen eingefuegt'.format(nextid-nr0), 0.80)

    # Unbefestigte Flaechen ------------------------------------------------------------------------

    # Falls Option check_difftezg gewählt: Erzeuge unbefestigte Flächen als Differenz aus
    # TEZG-Fläche und befestigten Flächen. Diese Differenz wird haltungsweise berechnet. 

    if check_difftezg:

        # Nur Daten fuer ausgewaehlte Teilgebiete
        if auswahl_Teilgebiete != "":
            auswahl = " WHERE flaechen.teilgebiet in ({:})".format(auswahl_Teilgebiete)
        else:
            auswahl = ""

        sql = u"""
          SELECT tezg.flnam, tezg.haltnam, area(tezg.geom) - sum(area(Intersection(tezg.geom,flaechen.geom))) AS flaeche, 
            tezg.neigkl AS neigkl, tezg.regenschreiber AS regenschreiber, 
            tezg.abflussparameter AS abflussparameter, tezg.createdat AS createdat, 
            tezg.kommentar AS kommentar
          FROM
            tezg INNER JOIN flaechen ON Intersects(tezg.geom,flaechen.geom)
          GROUP BY tezg.haltnam{:}
        """.format(auswahl)
        try:
            dbQK.sql(sql)
        except:
            fehlermeldung(u"(24) SQL-Fehler in QKan-DB: \n", sql)
            del dbQK
            del dbHE
            return False

        fortschritt('Export unbefestigte Flaechen...', 0.85)

        nr0 = nextid

        for attr in dbQK.fetchall():

            # In allen Feldern None durch NULL ersetzen
            (flnam, haltnam,  neigkl, flaeche, regenschreiber, abflussparameter, createdat, kommentar) = \
                ('NULL' if el is None else el for el in attr)

            # Datenkorrekturen
            
            spkonst = math.sqrt(flaeche)*2.
            splaufz = math.sqrt(flaeche)*6.

            if createdat == 'NULL':
                createdat = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())

            if kommentar is None or kommentar == '':
                kommentar = 'eingefuegt von k_qkhe'

            # befestigter Anteil
            sql = u"""
              INSERT INTO FLAECHE
              ( GROESSE, REGENSCHREIBER, HALTUNG, ANZAHLSPEICHER, 
                SPEICHERKONSTANTE, SCHWERPUNKTLAUFZEIT, BERECHNUNGSPEICHERKONSTANTE, TYP, 
                PARAMETERSATZ, NEIGUNGSKLASSE, NAME, LASTMODIFIED, 
                KOMMENTAR, ID, ZUORDNUNABHEZG)
              VALUES
              ( {flaeche:.4f}, {regenschreiber}, '{haltnam}', {anzsp},
                {spkonst:.3f}, {splaufz:.2f}, {berspkonst}, {fltyp},
                '{abflussparameter}', {neigkl}, 'f_{flnam}', '{createdat}',
                '{kommentar}', {nextid}, {zuordnunabhezg});
              """.format(flaeche = flaeche, regenschreiber = regenschreiber, haltnam = haltnam, anzsp = 3, 
                         spkonst = spkonst, splaufz = splaufz, berspkonst = 2, fltyp = 0, 
                         abflussparameter = abflussparameter, neigkl = neigkl, flnam = flnam, createdat = createdat, 
                         kommentar = kommentar, nextid = nextid, zuordnunabhezg = 0)
            try:
                dbHE.sql(sql)
            except:
                fehlermeldung(u"(10) SQL-Fehler in Firebird: \n", sql)
                del dbQK
                del dbHE
                return False

            nextid += 1
        dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
        dbHE.commit()

        fortschritt(u'{} Unbefestigte Flaechen eingefuegt aus tezg abzgl. bef. Flächen'.format(nextid-nr0), 0.85)

    # --------------------------------------------------------------------------------------------
    # Unbefestigte Flächen (Kriterium: Attribut abflussparameter.bodenklasse ist NULL

    # Nur Daten fuer ausgewaehlte Teilgebiete
    if auswahl_Teilgebiete != "":
        auswahl = " and flaechen.teilgebiet in ({:})".format(auswahl_Teilgebiete)
    else:
        auswahl = ""

    sql = u"""
      SELECT flaechen.flnam AS flnam, Coalesce(flaechen.haltnam,tezg.haltnam) AS haltnam,
        flaechen.neigkl AS neigkl,
        area(flaechen.geom) AS flaeche, flaechen.regenschreiber AS regenschreiber, 
        flaechen.abflussparameter AS abflussparameter, flaechen.createdat AS createdat, 
        flaechen.kommentar AS kommentar
      FROM flaechen LEFT JOIN abflussparameter
      ON flaechen.abflussparameter = abflussparameter.apnam
            LEFT JOIN tezg
      ON Within(Centroid(flaechen.geom),tezg.geom)
      WHERE abflussparameter.bodenklasse IS NOT NULL and
            Coalesce(flaechen.haltnam,tezg.haltnam) IS NOT NULL {:}
    """.format(auswahl)
    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(25) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False


    fortschritt('Export befestigte Flaechen...', 0.85)

    nr0 = nextid

    for attr in dbQK.fetchall():

        # In allen Feldern None durch NULL ersetzen
        (flnam, haltnam,  neigkl, flaeche, regenschreiber, abflussparameter, createdat, kommentar) = \
            ('NULL' if el is None else el for el in attr)

        # Datenkorrekturen
        
        spkonst = math.sqrt(flaeche)*2.
        splaufz = math.sqrt(flaeche)*6.

        if createdat == 'NULL':
            createdat = time.strftime('%d.%m.%Y %H:%M:%S',time.localtime())

        if kommentar is None or kommentar == '':
            kommentar = 'eingefuegt von QKan'

        # befestigter Anteil
        sql = u"""
          INSERT INTO FLAECHE
          ( GROESSE, REGENSCHREIBER, HALTUNG, ANZAHLSPEICHER, 
            SPEICHERKONSTANTE, SCHWERPUNKTLAUFZEIT, BERECHNUNGSPEICHERKONSTANTE, TYP, 
            PARAMETERSATZ, NEIGUNGSKLASSE, NAME, LASTMODIFIED, 
            KOMMENTAR, ID, ZUORDNUNABHEZG)
          VALUES
          ( {flaeche:.4f}, '{regenschreiber}', '{haltnam}', {anzsp},
            {spkonst:.3f}, {splaufz:.2f}, {berspkonst}, {fltyp},
            '{abflussparameter}', {neigkl}, 'f_{flnam}', '{createdat}',
            '{kommentar}', {nextid}, {zuordnunabhezg});
          """.format(flaeche = flaeche, regenschreiber = regenschreiber, haltnam = haltnam, anzsp = 3, 
                     spkonst = spkonst, splaufz = splaufz, berspkonst = 2, fltyp = 0, 
                     abflussparameter = abflussparameter, neigkl = neigkl, flnam = flnam, createdat = createdat, 
                     kommentar = kommentar, nextid = nextid, zuordnunabhezg = 0)
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(11) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False

        nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    fortschritt(u'{} Unbefestigte Flaechen aus unbefestigten Flächenobjekten eingefuegt'.format(nextid-nr0), 0.85)

    # -----------------------------------------------------------------------------------------
    # Bearbeitung in QKan: Vervollständigung der Teilgebiete
    """
      Prüfung der vorliegenden Teilgebiete in QKan
      ============================================
      Zunächst eine grundsätzliche Anmerkung: In HE gibt es keine Teilgebiete in der Form, wie sie
      in QKan vorhanden sind. Diese werden (nur) in QKan verwendet, um zum Einen die Grundlagendaten
       - einwohnerspezifischer Schmutzwasseranfall
       - Fremdwasseranteil
       - Stundenmittel
      zu verwalten und den tezg-Flächen zuzuordnen und zum Anderen, um die Möglichkeit zu haben,
      um für den Export Teile eines Netzes auszuwählen.

      Aus diesem Grund werden vor dem Export der Einzeleinleiter diese Daten geprüft:

      1 Wenn in QKan keine Teilgebiete vorhanden sind, wird zunächst geprüft, ob die
         tezg-Flächen einem (noch nicht angelegten) Teilgebiet zugeordnet sind.
         1.1 Keine tezg-Fläche ist einem Teilgebiet zugeordnet. Dann wird ein Teilgebiet angelegt
             und alle tezg-Flächen diesem Teilgebiet zugeordnet
         1.2 Die tezg-Flächen sind einem oder mehreren (noch nicht vorhandenen) Teilgebieten zugeordnet.
             Dann werden entsprechende Teilgebiete mit Standardwerten angelegt.
      2 Wenn in QKan Teilgebiete vorhanden sind, wird geprüft, ob es auch tezg-Flächen gibt, die diesen
         Teilgebieten zugeordnet sind.
         2.1 Es gibt keine tezg-Flächen, die einem Teilgebiet zugeordnet sind.
             2.1.1 Es gibt in QKan genau ein Teilgebiet. Dann werden alle tezg-Flächen diesem Teilgebiet
                   zugeordnet.
             2.1.2 Es gibt in QKan mehrere Teilgebiete. Dann werden alle tezg-Flächen geographisch dem
                   betreffenden Teilgebiet zugeordnet.
         2.2 Es gibt mindestens eine tezg-Fläche, die einem Teilgebiet zugeordnet ist.
             Dann wird geprüft, ob es noch nicht zugeordnete tezg-Flächen gibt, eine Warnung angezeigt und
             diese tezg-Flächen aufgelistet.
    """

    if check_tabinit:
        dbHE.sql("DELETE FROM TEILEINZUGSGEBIET")

    sql = 'SELECT count(*) AS anz FROM teilgebiete'
    dbQK.sql(sql)
    anztgb = int(dbQK.fetchone()[0])
    if anztgb == 0:
        # 1 Kein Teilgebiet in QKan -----------------------------------------------------------------
        createdat = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime())

        sql = u"""
            SELECT count(*) AS anz FROM tezg WHERE
            (teilgebiet is not NULL) and
            (teilgebiet <> 'NULL') and
            (teilgebiet <> '')
        """
        dbQK.sql(sql)
        anz = int(dbQK.fetchone()[0])
        if anz == 0:
            # 1.1 Keine tezg-Fläche mit Teilgebiet ----------------------------------------------------
            sql = u"""
               INSERT INTO teilgebiete
               ( tgnam, ewdichte, wverbrauch, stdmittel,
                 fremdwas, flaeche, kommentar, createdat, geom)
               Values
               ( 'Teilgebiet1', 60, 120, 14, 100, '{createdat}',
                 'Hinzugefuegt aus QKan')""".format(createdat=createdat)
            try:
                dbQK.sql(sql)
            except BaseException as err:
                fehlermeldung(u"(27) Fehler in SQL:\n{sql}\n", err)
                return False
            dbQK.commit()
        else:
            # 1.2 tezg-Flächen mit Teilgebiet ----------------------------------------------------
            # Liste der in allen tezg-Flächen vorkommenden Teilgebieten
            sql = 'SELECT teilgebiet FROM tezg WHERE teilgebiet is not NULL GROUP BY teilgebiet'
            dbQK.sql(sql)
            listeilgeb = dbQK.fetchall()
            for tgb in listeilgeb:
                sql = u"""
                   INSERT INTO teilgebiete
                   ( tgnam, ewdichte, wverbrauch, stdmittel,
                     fremdwas, flaeche, kommentar, createdat, geom)
                   Values
                   ( '{tgnam}', 60, 120, 14, 100, '{createdat}',
                     'Hinzugefuegt aus QKan')""".format(tgnam=tgb[0], createdat=createdat)
                try:
                    dbQK.sql(sql)
                except BaseException as err:
                    fehlermeldung(u"(28) Fehler in SQL:\n{sql}\n", err)
                    return False
                dbQK.commit()
                iface.messageBar().pushMessage(u"Tabelle 'teilgebiete':\n",
                                           u"Es wurden {} Teilgebiete hinzugefügt".format(len(tgb)),
                                           level=QgsMessageBar.INFO, duration=3)

            # Kontrolle mit Warnung
            sql = u"""
                SELECT count(*) AS anz
                FROM tezg
                LEFT JOIN teilgebiete ON tezg.teilgebiet = teilgebiete.tgnam
                WHERE teilgebiete.pk is NULL
            """
            dbQK.sql(sql)
            anz = int(dbQK.fetchone()[0])
            if anz > 0:
                iface.messageBar().pushMessage(u"Fehlerhafte Daten in Tabelle 'tezg':",
                    u"{} Flächen sind keinem Teilgebiet zugeordnet".format(anz),
                    level=QgsMessageBar.WARNING,duration=0)
    else:
        # 2 Teilgebiete in QKan ----------------------------------------------------
        sql = u"""
            SELECT count(*) AS anz
            FROM tezg
            INNER JOIN teilgebiete ON tezg.teilgebiet = teilgebiete.tgnam
        """
        dbQK.sql(sql)
        anz = int(dbQK.fetchone()[0])
        if anz == 0:
            # 2.1 Keine tezg-Fläche mit Teilgebiet ----------------------------------------------------
            if anztgb == 1:
                # 2.1.1 Es existiert genau ein Teilgebiet ---------------------------------------------
                sql = u"UPDATE tezg SET teilgebiet = (SELECT tgnam FROM teilgebiete GROUP BY tgnam)"
                try:
                    dbQK.sql(sql)
                except BaseException as err:
                    fehlermeldung(u"(29) Fehler in SQL:\n{sql}\n", err)
                    return False
                dbQK.commit()
                iface.messageBar().pushMessage(u"Tabelle 'tezg':\n",
                    u"Alle Flächen in der Tabelle 'tezg' wurden einem Teilgebiet zugeordnet",
                    level=QgsMessageBar.INFO, duration=3)
            else:
                # 2.1.2 Es existieren mehrere Teilgebiete ------------------------------------------
                sql = u"""UPDATE tezg SET teilgebiet = (SELECT tgnam FROM teilgebiete
                      WHERE within(centroid(tezg.geom),teilgebiete.geom))"""
                try:
                    dbQK.sql(sql)
                except BaseException as err:
                    fehlermeldung(u"(30) Fehler in SQL:\n{sql}\n", err)
                    return False
                dbQK.commit()
                iface.messageBar().pushMessage(u"Tabelle 'tezg':\n",
                    u"Alle Flächen in der Tabelle 'tezg' wurden dem Teilgebiet zugeordnet, in dem sie liegen.",
                    level=QgsMessageBar.INFO, duration=3)

                # Kontrolle mit Warnung
                sql = u"""
                    SELECT count(*) AS anz
                    FROM tezg
                    LEFT JOIN teilgebiete ON tezg.teilgebiet = teilgebiete.tgnam
                    WHERE teilgebiete.pk is NULL
                """
                dbQK.sql(sql)
                anz = int(dbQK.fetchone()[0])
                if anz > 0:
                    iface.messageBar().pushMessage(u"Fehlerhafte Daten in Tabelle 'tezg':",
                        u"{} Flächen sind keinem Teilgebiet zugeordnet".format(anz),
                        level=QgsMessageBar.WARNING,duration=0)
        else:
            # 2.2 Es gibt tezg mit zugeordnetem Teilgebiet
            # Kontrolle mit Warnung
            sql = u"""
                SELECT count(*) AS anz
                FROM tezg
                LEFT JOIN teilgebiete ON tezg.teilgebiet = teilgebiete.tgnam
                WHERE teilgebiete.pk is NULL
            """
            dbQK.sql(sql)
            anz = int(dbQK.fetchone()[0])
            if anz > 0:
                iface.messageBar().pushMessage(u"Fehlerhafte Daten in Tabelle 'tezg':",
                                               u"{} Flächen sind keinem Teilgebiet zugeordnet".format(anz),
                                               level=QgsMessageBar.WARNING, duration=0)

    # --------------------------------------------------------------------------------------------
    # Export der Einzeleinleiter aus Schmutzwasser
    #
    # Referenzlisten (HE 7.8):
    #
    # ABWASSERART (Im Formular "Art"):
    #    0 = Häuslich
    #    1 = Gewerblich
    #    2 = Industriell
    #    5 = Regenwasser
    # 
    # HERKUNFT (Im Formular "Herkunft"):
    #    0 = Siedlungstyp
    #    1 = Direkt
    #    2 = Frischwasserverbrauch
    #    3 = Einwohner
    #
    # Mit Stand 8.5.2017 ist nur die Variante HERKUNFT = 3 realisiert

    if check_tabinit:
        dbHE.sql("DELETE FROM EINZELEINLEITER")

    # Nur Daten fuer ausgewaehlte Teilgebiete
    if auswahl_Teilgebiete != "":
        auswahl = " WHERE g.teilgebiet in ({:}) ".format(auswahl_Teilgebiete)
    else:
        auswahl = ""

    # Abfrage fuer Herkunft = 3 (Einwohner)

    sql = u""" SELECT
      tezg.flnam AS flnam,
      x(centroid(tezg.geom)) AS xfl,
      y(centroid(tezg.geom)) AS yfl,
      tezg.haltnam AS haltnam,
      teilgebiete.ewdichte*area(tezg.geom)/10000. AS ew,
      teilgebiete.stdmittel AS stdmittel,
      teilgebiete.fremdwas AS fremdwas
    FROM tezg INNER JOIN teilgebiete ON tezg.teilgebiet = teilgebiete.tgnam
    """.format(auswahl)

    try:
        dbQK.sql(sql)
    except:
        fehlermeldung(u"(26) SQL-Fehler in QKan-DB: \n", sql)
        del dbQK
        del dbHE
        return False

    nr0 = nextid

    fortschritt('Export Einzeleinleiter...', 0.95)
    for b in dbQK.fetchall():

        # In allen Feldern None durch NULL ersetzen
        flnam, xfl, yfl, haltnam, ew, stdmittel, fremdwas = ('NULL' if el is None else el for el in b)

        # Einfuegen in die Datenbank
        sql = u"""
          INSERT INTO EINZELEINLEITER
          ( XKOORDINATE, YKOORDINATE, ZUORDNUNGGESPERRT, ZUORDNUNABHEZG, ROHR, 
            ABWASSERART, EINWOHNER, WASSERVERBRAUCH, HERKUNFT,
            STUNDENMITTEL, FREMDWASSERZUSCHLAG, FAKTOR, GESAMTFLAECHE, TEILEINZUGSGEBIET, ZUFLUSSMODELL, ZUFLUSSDIREKT, ZUFLUSS, PLANUNGSSTATUS, NAME, LASTMODIFIED, ID) VALUES 
          ( {xfl}, {yfl}, {zuordnunggesperrt}, {zuordnunabhezg}, '{haltnam}',
            {abwasserart}, {ew}, {wverbrauch}, {herkunft},
            {stdmittel}, {fremdwas}, {faktor}, {flaeche}, '{teilgebiet}',
            {zuflussmodell}, {zuflussdirekt}, {zufluss}, {planungsstatus}, '{flnam}_SW_TEZG',
            '{createdat}', {nextid});
          """.format(xfl = xfl, yfl = yfl, zuordnunggesperrt = 0, zuordnunabhezg = 1,  haltnam = haltnam,   
                     abwasserart = 0, ew = ew, wverbrauch = 0, herkunft = 3,
                     stdmittel = stdmittel, fremdwas = fremdwas, faktor = 1, flaeche = 0, teilgebiet = 'NULL',
                     zuflussmodell = 0, zuflussdirekt = 0, zufluss = 0, planungsstatus = 0, flnam = flnam,
                     createdat = createdat, nextid = nextid)
        try:
            dbHE.sql(sql)
        except:
            fehlermeldung(u"(12) SQL-Fehler in Firebird: \n", sql)
            del dbQK
            del dbHE
            return False

        nextid += 1
    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()


    fortschritt(u'{} Einzeleinleiter eingefuegt'.format(nextid - nr0), 0.95)

# --------------------------------------------------------------------------------------------------
# Setzen der internen Referenzen

# --------------------------------------------------------------------------------------------------
# 1. Schaechte: Anzahl Kanten

    # sql = u"""
        # select SCHACHT.ID, SCHACHT.NAME as schnam, count(*) as anz 
        # from SCHACHT join ROHR
        # on (SCHACHT.NAME = ROHR.SCHACHTOBEN or SCHACHT.NAME = ROHR.SCHACHTUNTEN) group by SCHACHT.ID, SCHACHT.NAME
    # """

# --------------------------------------------------------------------------------------------------
# 2. Haltungen (="ROHR"): Referenz zu Schaechten (="SCHACHT")

    sql = u"""
      UPDATE ROHR
      SET SCHACHTOBENREF = 
        (SELECT ID FROM SCHACHT WHERE SCHACHT.NAME = ROHR.SCHACHTOBEN)
      WHERE EXISTS (SELECT ID FROM SCHACHT WHERE SCHACHT.NAME = ROHR.SCHACHTOBEN)
    """
    try:
        dbHE.sql(sql)
    except:
        fehlermeldung(u"(13) SQL-Fehler in Firebird: \n", sql)
        del dbQK
        del dbHE
        return False

    sql = u"""
      UPDATE ROHR
      SET SCHACHTUNTENREF = 
        (SELECT ID FROM SCHACHT WHERE SCHACHT.NAME = ROHR.SCHACHTUNTEN)
      WHERE EXISTS (SELECT ID FROM SCHACHT WHERE SCHACHT.NAME = ROHR.SCHACHTUNTEN)
    """
    try:
        dbHE.sql(sql)
    except:
        fehlermeldung(u"(14) SQL-Fehler in Firebird: \n", sql)
        del dbQK
        del dbHE
        return False

    # --------------------------------------------------------------------------------------------------
# 3. Haltungen (="ROHR"): Referenz zu teileinzugsgebieten

    sql = u"""
      UPDATE ROHR
      SET TEILEINZUGSGEBIETREF = 
        (SELECT ID FROM TEILEINZUGSGEBIET WHERE TEILEINZUGSGEBIET.NAME = ROHR.TEILEINZUGSGEBIET)
      WHERE EXISTS (SELECT ID FROM TEILEINZUGSGEBIET WHERE TEILEINZUGSGEBIET.NAME = ROHR.TEILEINZUGSGEBIET)
    """
    try:
        dbHE.sql(sql)
    except:
        fehlermeldung(u"(15) SQL-Fehler in Firebird: \n", sql)
        del dbQK
        del dbHE
        return False

    # --------------------------------------------------------------------------------------------------
# 3. Abflussparameter: Referenz zu Bodenklasse

    sql = u"""
      UPDATE ABFLUSSPARAMETER
      SET BODENKLASSEREF = 
        (SELECT ID FROM BODENKLASSE WHERE BODENKLASSE.NAME = ABFLUSSPARAMETER.BODENKLASSE)
      WHERE EXISTS (SELECT ID FROM BODENKLASSE WHERE BODENKLASSE.NAME = ABFLUSSPARAMETER.BODENKLASSE)
    """
    try:
        dbHE.sql(sql)
    except:
        fehlermeldung(u"(16) SQL-Fehler in Firebird: \n", sql)
        del dbQK
        del dbHE
        return False

    dbHE.sql("UPDATE ITWH$PROGINFO SET NEXTID = {:d}".format(nextid))
    dbHE.commit()

    del dbQK
    del dbHE

    fortschritt('Ende...',1)

    iface.messageBar().pushMessage(u"Status: ", u"Datenexport abgeschlossen.",
        level=QgsMessageBar.INFO, duration=0)

# ----------------------------------------------------------------------------------------------------------------------

# Verzeichnis der Testdaten
pfad = 'C:/FHAC/jupiter/hoettges/team_data/Kanalprogramme/k_qkan/k_heqk/beispiele/modelldb_itwh'

database_HE =   os.path.join(pfad,'muster-modelldatenbank.idbf')
database_QKan = os.path.join(pfad,'muster.sqlite')

if __name__ == '__main__':
    exportKanaldaten(database_HE, database_QKan)
elif __name__ == '__console__':
    # QMessageBox.information(None, "Info", "Das Programm wurde aus der QGIS-Konsole aufgerufen")
    exportKanaldaten(database_HE, database_QKan)
elif __name__ == '__builtin__':
    # QMessageBox.information(None, "Info", "Das Programm wurde aus der QGIS-Toolbox aufgerufen")
    exportKanaldaten(database_HE, database_QKan)
# else:
    # QMessageBox.information(None, "Info", "Die Variable __name__ enthält: {0:s}".format(__name__))