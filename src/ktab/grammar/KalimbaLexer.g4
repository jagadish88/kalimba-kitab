// KalimbaLexer.g4 -- tokens for the kalimba / jianpu tab format (".ktab")
//
// The same characters mean different things in different places:
//   outside groups   spaces separate WORDS, newlines separate LINES
//   inside (...:     anything up to ':' is lyric text (commas, apostrophes...)
//   after ':'        digits, ' , / . - are note marks; spaces separate notes
// so the lexer switches modes at '(' , ':' and ')'.
lexer grammar KalimbaLexer;

// ---------- default mode: the layout of a line ----------
HEADER   : '@' ~[\r\n]* ;               // @title: Ami Chini Go Chini Tomare
LPAREN   : '(' -> pushMode(LYRIC) ;
REPEAT_STANZA : ':||' ;                 // end of a line: play the whole stanza twice
REPEAT_LINE   : ':|' ;                  // end of a line: play this line twice
BAR      : '|' ;                        // optional bar line
SPACE    : [ \t]+ ;                     // significant: a word break
// one or more blank lines (spaces allowed on them) end a stanza; listed
// before NEWLINE so the longest match wins
STANZA_BREAK : '\r'? '\n' ([ \t]* '\r'? '\n')+ ;
NEWLINE  : '\r'? '\n' ;                 // significant: a line break
BAD_CHAR : . ;                          // anything else: reported by the parser

// ---------- lyric: text up to the colon ----------
mode LYRIC;
LYRIC_TEXT : ~[:()\r\n]+ ;
COLON      : ':' -> mode(NOTES) ;
LYRIC_END  : ')' -> type(RPAREN), popMode ;          // "(re 6)": missing colon
LYRIC_NL   : '\r'? '\n' -> type(NEWLINE), popMode ; // unclosed group: recover
LYRIC_BAD  : '(' -> type(BAD_CHAR) ;

// ---------- notes: until the closing parenthesis ----------
mode NOTES;
DEGREE : [0-7] ;                        // 0 = rest, 1..7 = scale degrees
UP     : '\'' ;                         // octave up   (dot above)
DOWN   : ',' ;                          // octave down (dot below)
SLASH  : '/' ;                          // halves the length (one underline)
DOT    : '.' ;                          // dotted note (x 1.5)
DASH   : '-' ;                          // one more beat
NSPACE : [ \t]+ ;                       // separates notes in a group
RPAREN : ')' -> popMode ;
NOTES_NL  : '\r'? '\n' -> type(NEWLINE), popMode ;  // unclosed group: recover
NOTES_BAD : . -> type(BAD_CHAR) ;                    // 8, 9, letters, '(' ...
