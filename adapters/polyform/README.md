# Polyform-compatible raw export adapter

This independent adapter consumes the documented user-export layout. It does not import proprietary Polycam source or require the Polycam application at runtime. It preserves original archive bytes and hash, keeps native and corrected image/pose streams distinct, records calibration and coordinate conventions, emits a conversion report, and rejects ambiguous/malformed packages.
