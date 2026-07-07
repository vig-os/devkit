/* Trivial C extension for the native capability-module smoke test (#884). */
#include <Python.h>

static PyObject *
answer(PyObject *self, PyObject *args)
{
    (void) self;
    (void) args;
    return PyLong_FromLong(42);
}

static PyMethodDef methods[] = {
    { "answer", answer, METH_NOARGS, "Return 42." },
    { NULL, NULL, 0, NULL },
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "native_ext",
    NULL,
    -1,
    methods,
    NULL,
    NULL,
    NULL,
    NULL,
};

PyMODINIT_FUNC
PyInit_native_ext(void)
{
    return PyModule_Create(&module);
}
