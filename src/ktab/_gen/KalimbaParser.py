# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,20,157,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,1,0,5,0,
        28,8,0,10,0,12,0,31,9,0,1,0,3,0,34,8,0,1,0,1,0,1,0,5,0,39,8,0,10,
        0,12,0,42,9,0,1,0,3,0,45,8,0,1,0,3,0,48,8,0,1,0,1,0,1,1,1,1,1,1,
        1,2,1,2,1,2,5,2,58,8,2,10,2,12,2,61,9,2,1,3,3,3,64,8,3,1,3,1,3,1,
        3,5,3,69,8,3,10,3,12,3,72,9,3,1,3,3,3,75,8,3,1,3,3,3,78,8,3,1,3,
        3,3,81,8,3,1,4,1,4,1,5,1,5,3,5,87,8,5,1,6,4,6,90,8,6,11,6,12,6,91,
        1,7,1,7,3,7,96,8,7,1,7,1,7,3,7,100,8,7,1,7,1,7,1,7,5,7,105,8,7,10,
        7,12,7,108,9,7,1,7,3,7,111,8,7,1,7,1,7,1,8,1,8,3,8,117,8,8,1,9,1,
        9,3,9,121,8,9,1,9,3,9,124,8,9,1,9,3,9,127,8,9,1,9,5,9,130,8,9,10,
        9,12,9,133,9,9,1,10,4,10,136,8,10,11,10,12,10,137,1,10,4,10,141,
        8,10,11,10,12,10,142,3,10,145,8,10,1,11,4,11,148,8,11,11,11,12,11,
        149,1,12,4,12,153,8,12,11,12,12,12,154,1,12,0,0,13,0,2,4,6,8,10,
        12,14,16,18,20,22,24,0,2,1,0,7,8,1,0,3,4,170,0,29,1,0,0,0,2,51,1,
        0,0,0,4,54,1,0,0,0,6,63,1,0,0,0,8,82,1,0,0,0,10,86,1,0,0,0,12,89,
        1,0,0,0,14,93,1,0,0,0,16,116,1,0,0,0,18,118,1,0,0,0,20,144,1,0,0,
        0,22,147,1,0,0,0,24,152,1,0,0,0,26,28,3,2,1,0,27,26,1,0,0,0,28,31,
        1,0,0,0,29,27,1,0,0,0,29,30,1,0,0,0,30,33,1,0,0,0,31,29,1,0,0,0,
        32,34,7,0,0,0,33,32,1,0,0,0,33,34,1,0,0,0,34,35,1,0,0,0,35,40,3,
        4,2,0,36,37,5,7,0,0,37,39,3,4,2,0,38,36,1,0,0,0,39,42,1,0,0,0,40,
        38,1,0,0,0,40,41,1,0,0,0,41,44,1,0,0,0,42,40,1,0,0,0,43,45,7,0,0,
        0,44,43,1,0,0,0,44,45,1,0,0,0,45,47,1,0,0,0,46,48,5,6,0,0,47,46,
        1,0,0,0,47,48,1,0,0,0,48,49,1,0,0,0,49,50,5,0,0,1,50,1,1,0,0,0,51,
        52,5,1,0,0,52,53,7,0,0,0,53,3,1,0,0,0,54,59,3,6,3,0,55,56,5,8,0,
        0,56,58,3,6,3,0,57,55,1,0,0,0,58,61,1,0,0,0,59,57,1,0,0,0,59,60,
        1,0,0,0,60,5,1,0,0,0,61,59,1,0,0,0,62,64,5,6,0,0,63,62,1,0,0,0,63,
        64,1,0,0,0,64,65,1,0,0,0,65,70,3,10,5,0,66,67,5,6,0,0,67,69,3,10,
        5,0,68,66,1,0,0,0,69,72,1,0,0,0,70,68,1,0,0,0,70,71,1,0,0,0,71,74,
        1,0,0,0,72,70,1,0,0,0,73,75,5,6,0,0,74,73,1,0,0,0,74,75,1,0,0,0,
        75,77,1,0,0,0,76,78,3,8,4,0,77,76,1,0,0,0,77,78,1,0,0,0,78,80,1,
        0,0,0,79,81,5,6,0,0,80,79,1,0,0,0,80,81,1,0,0,0,81,7,1,0,0,0,82,
        83,7,1,0,0,83,9,1,0,0,0,84,87,3,12,6,0,85,87,5,5,0,0,86,84,1,0,0,
        0,86,85,1,0,0,0,87,11,1,0,0,0,88,90,3,14,7,0,89,88,1,0,0,0,90,91,
        1,0,0,0,91,89,1,0,0,0,91,92,1,0,0,0,92,13,1,0,0,0,93,95,5,2,0,0,
        94,96,5,10,0,0,95,94,1,0,0,0,95,96,1,0,0,0,96,97,1,0,0,0,97,99,5,
        11,0,0,98,100,5,18,0,0,99,98,1,0,0,0,99,100,1,0,0,0,100,101,1,0,
        0,0,101,106,3,16,8,0,102,103,5,18,0,0,103,105,3,16,8,0,104,102,1,
        0,0,0,105,108,1,0,0,0,106,104,1,0,0,0,106,107,1,0,0,0,107,110,1,
        0,0,0,108,106,1,0,0,0,109,111,5,18,0,0,110,109,1,0,0,0,110,111,1,
        0,0,0,111,112,1,0,0,0,112,113,5,19,0,0,113,15,1,0,0,0,114,117,3,
        18,9,0,115,117,3,24,12,0,116,114,1,0,0,0,116,115,1,0,0,0,117,17,
        1,0,0,0,118,120,5,12,0,0,119,121,3,20,10,0,120,119,1,0,0,0,120,121,
        1,0,0,0,121,123,1,0,0,0,122,124,3,22,11,0,123,122,1,0,0,0,123,124,
        1,0,0,0,124,126,1,0,0,0,125,127,5,16,0,0,126,125,1,0,0,0,126,127,
        1,0,0,0,127,131,1,0,0,0,128,130,5,17,0,0,129,128,1,0,0,0,130,133,
        1,0,0,0,131,129,1,0,0,0,131,132,1,0,0,0,132,19,1,0,0,0,133,131,1,
        0,0,0,134,136,5,13,0,0,135,134,1,0,0,0,136,137,1,0,0,0,137,135,1,
        0,0,0,137,138,1,0,0,0,138,145,1,0,0,0,139,141,5,14,0,0,140,139,1,
        0,0,0,141,142,1,0,0,0,142,140,1,0,0,0,142,143,1,0,0,0,143,145,1,
        0,0,0,144,135,1,0,0,0,144,140,1,0,0,0,145,21,1,0,0,0,146,148,5,15,
        0,0,147,146,1,0,0,0,148,149,1,0,0,0,149,147,1,0,0,0,149,150,1,0,
        0,0,150,23,1,0,0,0,151,153,5,17,0,0,152,151,1,0,0,0,153,154,1,0,
        0,0,154,152,1,0,0,0,154,155,1,0,0,0,155,25,1,0,0,0,27,29,33,40,44,
        47,59,63,70,74,77,80,86,91,95,99,106,110,116,120,123,126,131,137,
        142,144,149,154
    ]

class KalimbaParser ( Parser ):

    grammarFileName = "KalimbaParser.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "':||'", "':|'", 
                     "'|'", "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "':'", "<INVALID>", "'''", "','", "'/'", 
                     "'.'", "'-'" ]

    symbolicNames = [ "<INVALID>", "HEADER", "LPAREN", "REPEAT_STANZA", 
                      "REPEAT_LINE", "BAR", "SPACE", "STANZA_BREAK", "NEWLINE", 
                      "BAD_CHAR", "LYRIC_TEXT", "COLON", "DEGREE", "UP", 
                      "DOWN", "SLASH", "DOT", "DASH", "NSPACE", "RPAREN", 
                      "LYRIC_END" ]

    RULE_song = 0
    RULE_header = 1
    RULE_stanza = 2
    RULE_line = 3
    RULE_repeat = 4
    RULE_chunk = 5
    RULE_word = 6
    RULE_syllable = 7
    RULE_event = 8
    RULE_note = 9
    RULE_octave = 10
    RULE_duration = 11
    RULE_hold = 12

    ruleNames =  [ "song", "header", "stanza", "line", "repeat", "chunk", 
                   "word", "syllable", "event", "note", "octave", "duration", 
                   "hold" ]

    EOF = Token.EOF
    HEADER=1
    LPAREN=2
    REPEAT_STANZA=3
    REPEAT_LINE=4
    BAR=5
    SPACE=6
    STANZA_BREAK=7
    NEWLINE=8
    BAD_CHAR=9
    LYRIC_TEXT=10
    COLON=11
    DEGREE=12
    UP=13
    DOWN=14
    SLASH=15
    DOT=16
    DASH=17
    NSPACE=18
    RPAREN=19
    LYRIC_END=20

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class SongContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def stanza(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(KalimbaParser.StanzaContext)
            else:
                return self.getTypedRuleContext(KalimbaParser.StanzaContext,i)


        def EOF(self):
            return self.getToken(KalimbaParser.EOF, 0)

        def header(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(KalimbaParser.HeaderContext)
            else:
                return self.getTypedRuleContext(KalimbaParser.HeaderContext,i)


        def STANZA_BREAK(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.STANZA_BREAK)
            else:
                return self.getToken(KalimbaParser.STANZA_BREAK, i)

        def SPACE(self):
            return self.getToken(KalimbaParser.SPACE, 0)

        def NEWLINE(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.NEWLINE)
            else:
                return self.getToken(KalimbaParser.NEWLINE, i)

        def getRuleIndex(self):
            return KalimbaParser.RULE_song




    def song(self):

        localctx = KalimbaParser.SongContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_song)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 29
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==1:
                self.state = 26
                self.header()
                self.state = 31
                self._errHandler.sync(self)
                _la = self._input.LA(1)

            self.state = 33
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==7 or _la==8:
                self.state = 32
                _la = self._input.LA(1)
                if not(_la==7 or _la==8):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()


            self.state = 35
            self.stanza()
            self.state = 40
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,2,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 36
                    self.match(KalimbaParser.STANZA_BREAK)
                    self.state = 37
                    self.stanza() 
                self.state = 42
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,2,self._ctx)

            self.state = 44
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==7 or _la==8:
                self.state = 43
                _la = self._input.LA(1)
                if not(_la==7 or _la==8):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()


            self.state = 47
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==6:
                self.state = 46
                self.match(KalimbaParser.SPACE)


            self.state = 49
            self.match(KalimbaParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class HeaderContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def HEADER(self):
            return self.getToken(KalimbaParser.HEADER, 0)

        def NEWLINE(self):
            return self.getToken(KalimbaParser.NEWLINE, 0)

        def STANZA_BREAK(self):
            return self.getToken(KalimbaParser.STANZA_BREAK, 0)

        def getRuleIndex(self):
            return KalimbaParser.RULE_header




    def header(self):

        localctx = KalimbaParser.HeaderContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_header)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 51
            self.match(KalimbaParser.HEADER)
            self.state = 52
            _la = self._input.LA(1)
            if not(_la==7 or _la==8):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StanzaContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def line(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(KalimbaParser.LineContext)
            else:
                return self.getTypedRuleContext(KalimbaParser.LineContext,i)


        def NEWLINE(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.NEWLINE)
            else:
                return self.getToken(KalimbaParser.NEWLINE, i)

        def getRuleIndex(self):
            return KalimbaParser.RULE_stanza




    def stanza(self):

        localctx = KalimbaParser.StanzaContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_stanza)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 54
            self.line()
            self.state = 59
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,5,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 55
                    self.match(KalimbaParser.NEWLINE)
                    self.state = 56
                    self.line() 
                self.state = 61
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,5,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LineContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def chunk(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(KalimbaParser.ChunkContext)
            else:
                return self.getTypedRuleContext(KalimbaParser.ChunkContext,i)


        def SPACE(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.SPACE)
            else:
                return self.getToken(KalimbaParser.SPACE, i)

        def repeat(self):
            return self.getTypedRuleContext(KalimbaParser.RepeatContext,0)


        def getRuleIndex(self):
            return KalimbaParser.RULE_line




    def line(self):

        localctx = KalimbaParser.LineContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_line)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 63
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==6:
                self.state = 62
                self.match(KalimbaParser.SPACE)


            self.state = 65
            self.chunk()
            self.state = 70
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,7,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 66
                    self.match(KalimbaParser.SPACE)
                    self.state = 67
                    self.chunk() 
                self.state = 72
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,7,self._ctx)

            self.state = 74
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
            if la_ == 1:
                self.state = 73
                self.match(KalimbaParser.SPACE)


            self.state = 77
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==3 or _la==4:
                self.state = 76
                self.repeat()


            self.state = 80
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,10,self._ctx)
            if la_ == 1:
                self.state = 79
                self.match(KalimbaParser.SPACE)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RepeatContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def REPEAT_LINE(self):
            return self.getToken(KalimbaParser.REPEAT_LINE, 0)

        def REPEAT_STANZA(self):
            return self.getToken(KalimbaParser.REPEAT_STANZA, 0)

        def getRuleIndex(self):
            return KalimbaParser.RULE_repeat




    def repeat(self):

        localctx = KalimbaParser.RepeatContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_repeat)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 82
            _la = self._input.LA(1)
            if not(_la==3 or _la==4):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ChunkContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def word(self):
            return self.getTypedRuleContext(KalimbaParser.WordContext,0)


        def BAR(self):
            return self.getToken(KalimbaParser.BAR, 0)

        def getRuleIndex(self):
            return KalimbaParser.RULE_chunk




    def chunk(self):

        localctx = KalimbaParser.ChunkContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_chunk)
        try:
            self.state = 86
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [2]:
                self.enterOuterAlt(localctx, 1)
                self.state = 84
                self.word()
                pass
            elif token in [5]:
                self.enterOuterAlt(localctx, 2)
                self.state = 85
                self.match(KalimbaParser.BAR)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class WordContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def syllable(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(KalimbaParser.SyllableContext)
            else:
                return self.getTypedRuleContext(KalimbaParser.SyllableContext,i)


        def getRuleIndex(self):
            return KalimbaParser.RULE_word




    def word(self):

        localctx = KalimbaParser.WordContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_word)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 89 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 88
                self.syllable()
                self.state = 91 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==2):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SyllableContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAREN(self):
            return self.getToken(KalimbaParser.LPAREN, 0)

        def COLON(self):
            return self.getToken(KalimbaParser.COLON, 0)

        def event(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(KalimbaParser.EventContext)
            else:
                return self.getTypedRuleContext(KalimbaParser.EventContext,i)


        def RPAREN(self):
            return self.getToken(KalimbaParser.RPAREN, 0)

        def LYRIC_TEXT(self):
            return self.getToken(KalimbaParser.LYRIC_TEXT, 0)

        def NSPACE(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.NSPACE)
            else:
                return self.getToken(KalimbaParser.NSPACE, i)

        def getRuleIndex(self):
            return KalimbaParser.RULE_syllable




    def syllable(self):

        localctx = KalimbaParser.SyllableContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_syllable)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 93
            self.match(KalimbaParser.LPAREN)
            self.state = 95
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==10:
                self.state = 94
                self.match(KalimbaParser.LYRIC_TEXT)


            self.state = 97
            self.match(KalimbaParser.COLON)
            self.state = 99
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==18:
                self.state = 98
                self.match(KalimbaParser.NSPACE)


            self.state = 101
            self.event()
            self.state = 106
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,15,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 102
                    self.match(KalimbaParser.NSPACE)
                    self.state = 103
                    self.event() 
                self.state = 108
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,15,self._ctx)

            self.state = 110
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==18:
                self.state = 109
                self.match(KalimbaParser.NSPACE)


            self.state = 112
            self.match(KalimbaParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class EventContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def note(self):
            return self.getTypedRuleContext(KalimbaParser.NoteContext,0)


        def hold(self):
            return self.getTypedRuleContext(KalimbaParser.HoldContext,0)


        def getRuleIndex(self):
            return KalimbaParser.RULE_event




    def event(self):

        localctx = KalimbaParser.EventContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_event)
        try:
            self.state = 116
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [12]:
                self.enterOuterAlt(localctx, 1)
                self.state = 114
                self.note()
                pass
            elif token in [17]:
                self.enterOuterAlt(localctx, 2)
                self.state = 115
                self.hold()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NoteContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DEGREE(self):
            return self.getToken(KalimbaParser.DEGREE, 0)

        def octave(self):
            return self.getTypedRuleContext(KalimbaParser.OctaveContext,0)


        def duration(self):
            return self.getTypedRuleContext(KalimbaParser.DurationContext,0)


        def DOT(self):
            return self.getToken(KalimbaParser.DOT, 0)

        def DASH(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.DASH)
            else:
                return self.getToken(KalimbaParser.DASH, i)

        def getRuleIndex(self):
            return KalimbaParser.RULE_note




    def note(self):

        localctx = KalimbaParser.NoteContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_note)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 118
            self.match(KalimbaParser.DEGREE)
            self.state = 120
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==13 or _la==14:
                self.state = 119
                self.octave()


            self.state = 123
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==15:
                self.state = 122
                self.duration()


            self.state = 126
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==16:
                self.state = 125
                self.match(KalimbaParser.DOT)


            self.state = 131
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==17:
                self.state = 128
                self.match(KalimbaParser.DASH)
                self.state = 133
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class OctaveContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def UP(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.UP)
            else:
                return self.getToken(KalimbaParser.UP, i)

        def DOWN(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.DOWN)
            else:
                return self.getToken(KalimbaParser.DOWN, i)

        def getRuleIndex(self):
            return KalimbaParser.RULE_octave




    def octave(self):

        localctx = KalimbaParser.OctaveContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_octave)
        self._la = 0 # Token type
        try:
            self.state = 144
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [13]:
                self.enterOuterAlt(localctx, 1)
                self.state = 135 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while True:
                    self.state = 134
                    self.match(KalimbaParser.UP)
                    self.state = 137 
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if not (_la==13):
                        break

                pass
            elif token in [14]:
                self.enterOuterAlt(localctx, 2)
                self.state = 140 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                while True:
                    self.state = 139
                    self.match(KalimbaParser.DOWN)
                    self.state = 142 
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if not (_la==14):
                        break

                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class DurationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def SLASH(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.SLASH)
            else:
                return self.getToken(KalimbaParser.SLASH, i)

        def getRuleIndex(self):
            return KalimbaParser.RULE_duration




    def duration(self):

        localctx = KalimbaParser.DurationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_duration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 147 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 146
                self.match(KalimbaParser.SLASH)
                self.state = 149 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==15):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class HoldContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def DASH(self, i:int=None):
            if i is None:
                return self.getTokens(KalimbaParser.DASH)
            else:
                return self.getToken(KalimbaParser.DASH, i)

        def getRuleIndex(self):
            return KalimbaParser.RULE_hold




    def hold(self):

        localctx = KalimbaParser.HoldContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_hold)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 152 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 151
                self.match(KalimbaParser.DASH)
                self.state = 154 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==17):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





