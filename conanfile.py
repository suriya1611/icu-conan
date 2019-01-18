from conans import ConanFile, tools, AutoToolsBuildEnvironment
import os,shutil
import glob


class IcuConan(ConanFile):
    name = "icu"
    version = "63.1"
    homepage = "https://site.icu-projec.org"
    settings = "os", "arch", "compiler", "build_type","os_build","arch_build"
    source_url = "https://github.com/unicode-org/icu/archive/release-{0}.tar.gz".format(version.replace('.', '-'))

    options = {"shared":[True,False],
                "data_packaging":["files","archive","library","static"],
                "with_unit_tests":[True,False],
                "silent":[True,False]}

    default_options = {"shared":False,
                        "data_packaging":"static",
                        "with_unit_tests":False,
                        "silent":True}

    cfg = {'enable_debug': '',
           'platform': '',
           'host': '',
           'arch_bits': '',
           'cross_build_dir':'',
           'cross_build_output_dir':'',
           'output_dir': '',
           'enable_static': '',
           'data_packaging': '',
           'general_opts': ''}

    android_triple_host = {"armv7":"arm-linux-androideabi",
                            "armv8":"aarch64-linux-android",
                            "x86":"i686-linux-android",
                            "x86_64":"x86_64-linux-android"}

    ios_triple_host = { 'armv7':'arm-apple-darwin',
                        'armv8':'arm-apple-dawrin',
                        'x86':'i386-apple-dawin',
                        'x86_64':'x86_64-apple-darwin'}

    cross_compiling = False

    def build_requirements(self):
        if self.settings.os == "Windows":
            self.build_requires("cygwin_installer/2.9.0@bincrafters/stable")
            if self.settings.compiler != "Visual Studio":
                self.build_requires("mingw_installer/1.0@conan/stable")
        if self.settings.os == "Android":
            if self.settings.os_build == "Macos":
                self.build_requires("icu-cross-build/63.1@suriya/testing")
            if self.settings.os_build == "Linux":
                self.build_requires("icu-cross-build/63.1@suriya/testing")

    def imports(self):
        if self.settings.os == "Android" or self.settings.os == "iOS":
            self.copy("*","cross_build_dir/","cross_build_dir/")


    def configure(self):
        if self.settings.compiler in ["gcc","clang"]:
            self.settings.compiler.libcxx = 'libstdc++11'
        if self.settings.os != self.settings.os_build:
            if self.settings.os == "Windows" or self.settings.os == "Macos" or self.settings.os == "Linux":
                raise ConanInvalidConfiguration("Cannot Cross Compile from {0} to {1}".format(self.settings.os_build,self.settings.os))
            else:
                self.cross_compiling = True

    def source(self):
        self.output.info("Fetching sources: {0}".format(self.source_url))
        tools.get("{0}".format(self.source_url))
        os.rename("{0}-release-{1}".format(self.name, self.version.replace('.', '-')), 'sources')

    def build(self):
        if self.cross_compiling == True:
            self.output.info("Cross Compiling from {0} to {1}".format(self.settings.os_build,self.settings.os))

        if self.settings.compiler == 'Visual Studio':
            runConfigureICU_file = os.path.join('sources', 'icu4c', 'source', 'runConfigureICU')

            if self.settings.build_type == 'Release':
                tools.replace_in_file(runConfigureICU_file, "-MD", "-%s" % self.settings.compiler.runtime)
            if self.settings.build_type == 'Debug':
                tools.replace_in_file(runConfigureICU_file, "-MDd", "-%s -FS" % self.settings.compiler.runtime)

        self.cfg['icu_source_dir'] = os.path.join(self.build_folder, 'sources', 'icu4c', 'source')
        self.cfg['build_dir'] = os.path.join(self.build_folder, 'sources', 'icu4c', 'build')
        if self.cross_compiling == True:
            self.cfg['cross_build_dir'] = os.path.join(self.build_folder,'cross_build_dir')
        self.cfg['output_dir'] = os.path.join(self.build_folder, 'output')

        self.cfg['silent'] = '--silent' if self.options.silent else 'VERBOSE=1'
        self.cfg['enable_debug'] = '--enable-debug --disable-release' if self.settings.build_type == 'Debug' else ''

        if self.settings.arch in ["x86_64","armv8","mips64"]:
            self.cfg['arch_bits'] = '64' 
        else:
            self.cfg['arch_bits'] = '32'

        self.cfg['enable_static'] = '--enable-static --disable-shared' if not self.options.shared else '--enable-shared --disable-static'
        self.cfg['data_packaging'] = '--with-data-packaging={0}'.format(self.options.data_packaging)

        self.cfg['general_opts'] = '--disable-samples --disable-layout --disable-layoutex --disable-dyload'
        if not self.options.with_unit_tests:
            self.cfg['general_opts'] += ' --disable-tests'

        if self.settings.compiler == 'Visual Studio':
            # this overrides pre-configured environments (such as Appveyor's)
            if "VisualStudioVersion" in os.environ:
                del os.environ["VisualStudioVersion"]
            self.cfg['vccmd'] = tools.vcvars_command(self.settings)
            self._build_cygwin_msvc()
        else:
            self._build_autotools()

    def package(self):
        self.copy("LICENSE", dst=".", src=os.path.join(self.source_folder, 'sources', 'icu4c'))

        bin_dir_src, include_dir_src, lib_dir_src, share_dir_src = (os.path.join('output', path) for path in
                                                                    ('bin', 'include', 'lib', 'share'))
        if self.settings.os == 'Windows':
            bin_dir_dst, lib_dir_dst = ('bin64', 'lib64') if self.settings.arch == 'x86_64' else ('bin', 'lib')

            # we copy everything for a full ICU package
            self.copy("*", dst=bin_dir_dst, src=bin_dir_src, keep_path=True, symlinks=True)
            self.copy(pattern='*.dll', dst=bin_dir_dst, src=lib_dir_src, keep_path=False)
            self.copy("*", dst=lib_dir_dst, src=lib_dir_src, keep_path=True, symlinks=True)

            # lets remove .dlls from the lib dir, they are in bin/ in upstream releases.
            if os.path.exists(os.path.join(self.package_folder, lib_dir_dst)):
                for item in os.listdir(os.path.join(self.package_folder, lib_dir_dst)):
                    if item.endswith(".dll"):
                        os.remove(os.path.join(self.package_folder, lib_dir_dst, item))

            self.copy("*", dst="include", src=include_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="share", src=share_dir_src, keep_path=True, symlinks=True)
        else:
            # we copy everything for a full ICU package
            self.copy("*", dst="bin", src=bin_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="include", src=include_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="lib", src=lib_dir_src, keep_path=True, symlinks=True)
            self.copy("*", dst="share", src=share_dir_src, keep_path=True, symlinks=True)

    def package_id(self):
        # ICU unit testing shouldn't affect the package's ID
        self.info.options.with_unit_tests = "any"

        # Verbosity doesn't affect package's ID
        self.info.options.silent = "any"

    def package_info(self):
        bin_dir, lib_dir = ('bin64', 'lib64') if self.settings.arch == 'x86_64' and self.settings.os == 'Windows' else ('bin', 'lib')
        self.cpp_info.libdirs = [lib_dir]

        # if icudata is not last, it fails to build on some platforms (Windows)
        # some linkers are not clever enough to be able to link
        self.cpp_info.libs = []
        vtag = self.version.split('.')[0]
        keep1 = False
        keep2 = False
        for lib in tools.collect_libs(self, lib_dir):
            if not vtag in lib:
                if 'icudata' in lib or 'icudt' in lib:
                    keep1 = lib
                elif 'icuuc' in lib:
                    keep2 = lib
                else:
                    self.cpp_info.libs.append(lib)

        if keep2:
            self.cpp_info.libs.append(keep2)
        if keep1:
            self.cpp_info.libs.append(keep1)

        data_dir = os.path.join(self.package_folder, 'share', self.name, self.version)
        data_file = "icudt{v}l.dat".format(v=vtag)
        data_path = os.path.join(data_dir, data_file).replace('\\', '/')
        self.env_info.ICU_DATA.append(data_path)

        self.env_info.PATH.append(os.path.join(self.package_folder, bin_dir))

        if not self.options.shared:
            self.cpp_info.defines.append("U_STATIC_IMPLEMENTATION")
            if self.settings.os == 'Linux':
                self.cpp_info.libs.append('dl')
                
            if self.settings.os == 'Windows':
                self.cpp_info.libs.append('advapi32')
                
        if self.settings.compiler in ["gcc", "clang"]:
            self.cpp_info.cppflags = ["-std=c++11"]

    def build_config_cmd(self):
        if self.cross_compiling == True:
            outdir = self.cfg['cross_build_output_dir']
            if self.settings.os_build == 'Windows':
                if self.settings.compiler == "Visual Studio":
                    self.cfg['platform'] = "Cygwin/MSVC"
                else:
                    self.cfg['platform'] = "MinGW"
            elif self.settings.os_build == "Macos":
                self.cfg['platform'] = "MacOSX"
            elif self.settings.os_build == "Linux":
                self.cfg['platform'] = "Linux"
        else:
            outdir = self.cfg['output_dir'].replace('\\', '/')

        #outdir = tools.unix_path(self.cfg['output_dir'])

        #if self.options.msvc_platform == 'cygwin':
        #outdir = re.sub(r'([a-z]):(.*)',
        #                '/cygdrive/\\1\\2',
        #                self.cfg['output_dir'],
        #                flags=re.IGNORECASE).replace('\\', '/')

        config_cmd = "../source/runConfigureICU {enable_debug} " \
                     "{platform} {host} {lib_arch_bits} {outdir} " \
                     "{enable_static} {data_packaging} {general}" \
                     "".format(enable_debug=self.cfg['enable_debug'],
                               platform=self.cfg['platform'],
                               host=self.cfg['host'],
                               lib_arch_bits='--with-library-bits=%s' % self.cfg['arch_bits'],
                               outdir='--prefix=%s' % outdir,
                               enable_static=self.cfg['enable_static'],
                               data_packaging=self.cfg['data_packaging'],
                               general=self.cfg['general_opts'])

        return config_cmd

    def build_config_cmd_for_cross_build(self):
        outdir = self.cfg['output_dir'].replace('\\', '/')

        host_for_cross_build = ''
        if self.settings.os == 'Android':
            if self.settings.arch == 'armv7':
                host_for_cross_build = self.android_triple_host['armv7']
            elif self.settings.arch == 'armv8':
                host_for_cross_build = self.android_triple_host['armv8']
            elif self.settings.arch == 'x86':
                host_for_cross_build = self.android_triple_host['x86']
            else:
                host_for_cross_build = self.android_triple_host['x86_64']
        if self.settings.os == 'iOS':
            host_for_cross_build = self.ios_triple_host[self.settings.arch]
           
        config_cmd_for_cross_build = "../source/configure {enable_debug} " \
                     "{host} {outdir} " \
                     "{enable_static} {data_packaging} {cross_build_dir} {general}" \
                     "".format(enable_debug=self.cfg['enable_debug'],
                               host='--host=%s' % host_for_cross_build,
                               outdir='--prefix=%s' % outdir,
                               enable_static=self.cfg['enable_static'],
                               data_packaging=self.cfg['data_packaging'],
                               cross_build_dir='--with-cross-build=%s' % self.cfg['cross_build_dir'],
                               general=self.cfg['general_opts'])
        
        return config_cmd_for_cross_build
                    

    def _build_cygwin_msvc(self):
        self.cfg['platform'] = 'Cygwin/MSVC'

        if 'CYGWIN_ROOT' not in os.environ:
            raise Exception("CYGWIN_ROOT environment variable must be set.")
        else:
            self.output.info("Using Cygwin from: " + os.environ["CYGWIN_ROOT"])

        os.environ['PATH'] = os.path.join(os.environ['CYGWIN_ROOT'], 'bin') + os.pathsep + \
                             os.path.join(os.environ['CYGWIN_ROOT'], 'usr', 'bin') + os.pathsep + \
                             os.environ['PATH']

        os.mkdir(self.cfg['build_dir'])

        self.output.info("Starting configuration.")

        config_cmd = self.build_config_cmd()
        self.run("{vccmd} && cd {builddir} && bash -c '{config_cmd}'".format(vccmd=self.cfg['vccmd'],
                                                                             builddir=self.cfg['build_dir'],
                                                                             config_cmd=config_cmd))

        self.output.info("Starting built.")

        self.run("{vccmd} && cd {builddir} && make {silent} -j {cpus_var}".format(vccmd=self.cfg['vccmd'],
                                                                                  builddir=self.cfg['build_dir'],
                                                                                  silent=self.cfg['silent'],
                                                                                  cpus_var=tools.cpu_count()))
        if self.options.with_unit_tests:
            self.run("{vccmd} && cd {builddir} && make {silent} check".format(vccmd=self.cfg['vccmd'],
                                                                              builddir=self.cfg['build_dir'],
                                                                              silent=self.cfg['silent']))

        self.run("{vccmd} && cd {builddir} && make {silent} install".format(vccmd=self.cfg['vccmd'],
                                                                            builddir=self.cfg['build_dir'],
                                                                            silent=self.cfg['silent']))

    def _build_autotools(self):
        env_build = AutoToolsBuildEnvironment(self)
        if not self.options.shared:
            env_build.defines.append("U_STATIC_IMPLEMENTATION")
        if tools.is_apple_os(self.settings.os) and self.settings.get_safe("os.version"):
            env_build.flags.append(tools.apple_deployment_target_flag(self.settings.os,
                                                                      self.settings.os.version))

        with tools.environment_append(env_build.vars):
            if self.settings.os == 'Linux':
                self.cfg['platform'] = 'Linux/gcc' if str(self.settings.compiler).startswith('gcc') else 'Linux'
            elif self.settings.os == 'Macos':
                self.cfg['platform'] = 'MacOSX'
            elif self.settings.os == "Android":
                self.cfg['platform'] = ''
            elif self.settings.os == "iOS":
                self.cfg['platform'] =''
            if self.settings.os == 'Windows':
                self.cfg['platform'] = 'MinGW'

                if self.settings.arch == 'x86':
                    MINGW_CHOST = 'i686-w64-mingw32'
                else:
                    MINGW_CHOST = 'x86_64-w64-mingw32'

                self.cfg['host'] = '--build={MINGW_CHOST} ' \
                                   '--host={MINGW_CHOST} '.format(MINGW_CHOST=MINGW_CHOST)
            
            if self.cross_compiling == True:
                os.mkdir(self.cfg['build_dir'])
                self.output.info("Compiling for the host platform:{0}-{1}".format(self.settings.os,self.settings.arch))
                cross_build_config_cmd = self.build_config_cmd_for_cross_build()
                self.run("cd {builddir} && bash -c '{config_cmd}'".format(builddir=self.cfg['build_dir'],
                                                                        config_cmd=cross_build_config_cmd))
                os.system("cd {builddir} && make {silent} -j {cpus_var}".format(builddir=self.cfg['build_dir'],
                                                                                cpus_var=tools.cpu_count(),
                                                                                silent=self.cfg['silent']))

                os.system("cd {builddir} && make {silent} install".format(builddir=self.cfg['build_dir'],
                                                                        silent=self.cfg['silent']))

            else:
                os.mkdir(self.cfg['build_dir'])
                config_cmd = self.build_config_cmd()
                # with tools.environment_append(env_build.vars):
                self.run("cd {builddir} && bash -c '{config_cmd}'".format(builddir=self.cfg['build_dir'],
                                                                        config_cmd=config_cmd))
                os.system("cd {builddir} && make {silent} -j {cpus_var}".format(builddir=self.cfg['build_dir'],
                                                                                cpus_var=tools.cpu_count(),
                                                                                silent=self.cfg['silent']))
                if self.options.with_unit_tests:
                    os.system("cd {builddir} && make {silent} check".format(builddir=self.cfg['build_dir'],
                                                                            silent=self.cfg['silent']))
                os.system("cd {builddir} && make {silent} install".format(builddir=self.cfg['build_dir'],
                                                                        silent=self.cfg['silent']))

            if self.settings.os == 'Macos':
                with tools.chdir('output/lib'):
                    for dylib in glob.glob('*icu*.{0}.dylib'.format(self.version)):
                        self.run('install_name_tool -id {0} {1}'.format(
                            os.path.basename(dylib), dylib))   

        