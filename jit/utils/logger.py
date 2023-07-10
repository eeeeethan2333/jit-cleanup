import logging

logging.basicConfig(level=logging.INFO)
jit_logger = logging.getLogger("jit-cleaner")

# Convenient methods in order of verbosity from highest to lowest
# jit_logger.debug("debug will get printed")
# jit_logger.info("info will get printed")
# jit_logger.warning("warning will get printed")
# jit_logger.error("error will get printed")
# jit_logger.critical("critical will get printed")
