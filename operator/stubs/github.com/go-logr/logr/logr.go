package logr

type Logger struct{}

type LogSink interface{}

func (Logger) Info(string, ...any)         {}
func (Logger) Error(error, string, ...any) {}
func (Logger) WithValues(...any) Logger    { return Logger{} }
func (Logger) WithName(string) Logger      { return Logger{} }
func (Logger) GetSink() LogSink            { return nil }
