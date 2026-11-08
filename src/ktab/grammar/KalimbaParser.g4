// KalimbaParser.g4 -- structure of a kalimba / jianpu tab (".ktab")
//
//   @title: Ami Chini Go Chini Tomare          optional header lines
//   (A: 5/)(mi: 6/) (chi: 7/)(ni: 7/) (go: 7/)  one printed line
//                                              blank line(s) = new stanza
//   (O: 5/)(go: 6// 7//) (bi: 1'/)(de: 7/ 5/.) :|  line ends with :|  -> play it twice
//   (Tu: 7/)(mi: 1'/) (pa: 3'.)(re: 2') :||       line ends with :|| -> repeat the stanza
//
// Groups written with no space between them are one word ("A-mi");
// a space starts a new word.
parser grammar KalimbaParser;
options { tokenVocab = KalimbaLexer; }

// a song is one or more stanzas separated by blank lines
song     : header* (NEWLINE | STANZA_BREAK)? stanza (STANZA_BREAK stanza)* (NEWLINE | STANZA_BREAK)? SPACE? EOF ;
header   : HEADER (NEWLINE | STANZA_BREAK) ;

stanza   : line (NEWLINE line)* ;                    // consecutive non-blank lines
line     : SPACE? chunk (SPACE chunk)* SPACE? repeat? SPACE? ;   // never empty
repeat   : REPEAT_LINE                               // ... :|   play this line twice
         | REPEAT_STANZA                             // ... :||  play the stanza twice (last line only)
         ;
chunk    : word | BAR ;
word     : syllable+ ;                               // no spaces inside a word

// (lyric: notes)  -- the lyric may be empty: ( : 5)
syllable : LPAREN LYRIC_TEXT? COLON NSPACE? event (NSPACE event)* NSPACE? RPAREN ;

event    : note                                      // 5  1'//  7''/.  4--
         | hold                                      // a lone '-' mid-group
         ;
note     : DEGREE octave? duration? DOT? DASH* ;
octave   : UP+ | DOWN+ ;                             // 1'  1''  5,  5,,
duration : SLASH+ ;                                  // /=1/2  //=1/4  ///=1/8 beat
hold     : DASH+ ;
