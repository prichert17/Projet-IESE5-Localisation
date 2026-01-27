cmake_minimum_required(VERSION 3.20.0)

# 1. On pointe vers le dossier 'platform' car il contient le dossier 'zephyr'
list(APPEND ZEPHYR_EXTRA_MODULES ${CMAKE_CURRENT_SOURCE_DIR}/lib/dw3000-decadriver-source-master/platform)

# 2. Ensuite on charge Zephyr
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(UWB-test)

target_sources(app PRIVATE src/main.c)