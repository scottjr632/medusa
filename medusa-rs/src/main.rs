use std::fs::File;
use std::io::{self, BufRead, BufReader, Write};
use std::path::Path;
use std::{env, error::Error, fmt, fs};

static MEDUSA_CWD_KEY: &str = "__medusa_cwd_key__";

static DELIMITER: &str = "=";
static FILE_NAME: &str = ".medusa";
static CACHE_DIR: &str = "/tmp/medusa";

#[derive(Debug)]
struct CacheNotFound;

impl Error for CacheNotFound {}

impl fmt::Display for CacheNotFound {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "The cache could not be found")
    }
}

#[derive(Debug)]
struct ConfigNotFound;

impl Error for ConfigNotFound {}

impl fmt::Display for ConfigNotFound {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "The config file could not be found")
    }
}

#[derive(Debug, Clone)]
struct Executable {
    key: String,
    value: String,
}

impl fmt::Display for Executable {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "key: {} value: {}", self.key, self.value)
    }
}

fn invariant(check: bool, msg: String) -> () {
    if !check {
        panic!("{}", msg)
    }
}

fn get_cache_file() -> String {
    let ppid = nix::unistd::getppid();
    format!("{}/{}", CACHE_DIR, ppid)
}

fn get_does_cache_file_exist() -> bool {
    let cache_file_path = get_cache_file();
    return Path::new(&cache_file_path).exists();
}

fn get_does_config_file_exist() -> bool {
    return Path::new(FILE_NAME).exists();
}

fn get_is_subdirectory_of_cached_cwd() -> bool {
    let cached_cwd = match get_cached_cwd() {
        Ok(cached) => cached,
        Err(_) => return false,
    };
    let cwd = env::current_dir().unwrap();
    let cwd_str = cwd
        .into_os_string()
        .into_string()
        .expect("unable to convert PathBuf to string");

    return cwd_str.starts_with(&cached_cwd);
}

fn read_lines<P>(filename: P) -> io::Result<io::Lines<io::BufReader<File>>>
where
    P: AsRef<Path>,
{
    let file = File::open(filename)?;
    Ok(io::BufReader::new(file).lines())
}

fn get_current_set_aliases() -> Result<Vec<String>, Box<dyn Error>> {
    if !Path::new(&get_cache_file()).exists() {
        return Err(CacheNotFound.into());
    }

    let log_file_path = get_cache_file();
    let mut res: Vec<String> = vec![];
    let lines = read_lines(log_file_path)?;
    for (i, line) in lines.into_iter().enumerate() {
        if i == 0 {
            continue;
        }

        let line_val = line?;
        let line_val_without_newline = line_val.trim_end_matches("\n");
        res.push(format!("unalias {}", line_val_without_newline.to_string()));
    }

    Ok(res)
}

fn get_executables_from_config_file() -> Result<Vec<Executable>, Box<dyn Error>> {
    if !Path::new(FILE_NAME).exists() {
        return Err(ConfigNotFound.into());
    }

    let mut executables = vec![];
    let lines = read_lines(FILE_NAME)?;

    for line in lines {
        let line_val = line?;
        let val_without_newline = line_val.trim_end_matches("\n");
        let key_value_pair: Vec<&str> = val_without_newline.split(DELIMITER).collect();
        invariant(
            key_value_pair.len() == 2,
            format!("invalid key pair for line : {}", val_without_newline),
        );

        executables.push(Executable {
            key: key_value_pair[0].to_string(),
            value: key_value_pair[1].to_string(),
        })
    }

    Ok(executables)
}

fn format_execs_as_alias_cmd_string(execs: Vec<Executable>) -> String {
    let cmds: Vec<String> = execs
        .into_iter()
        .map(|exec| format!("alias {}=\"{}\"", exec.key, exec.value))
        .collect();

    cmds.join("; ")
}

fn get_cached_cwd() -> Result<String, CacheNotFound> {
    let cache_file_path = get_cache_file();
    if !Path::new(&cache_file_path).exists() {
        return Err(CacheNotFound);
    }

    let file = File::open(cache_file_path).expect("unable to find cache file");
    let reader = BufReader::new(file);

    for (i, line) in reader.lines().enumerate() {
        if i > 0 {
            return Err(CacheNotFound);
        }

        let line_val = line.expect("invalid line");
        invariant(
            line_val.starts_with(MEDUSA_CWD_KEY),
            "invalid cache line".into(),
        );

        let key_value: Vec<&str> = line_val.split(DELIMITER).collect();
        invariant(key_value.len() == 2, "invalid key value pair".into());

        let cwd = key_value[1].trim_end_matches("\n");
        return Ok(cwd.into());
    }
    panic!("reached unreachable point");
}

fn create_cache_content() -> Result<String, Box<dyn Error>> {
    let cwd = env::current_dir()?;
    let cwd_str = cwd
        .into_os_string()
        .into_string()
        .expect("unable to convert PathBuf to string");
    let mut contents: Vec<String> = vec![];
    contents.push(format!("{}={}", MEDUSA_CWD_KEY, cwd_str,));
    let execs = get_executables_from_config_file()?;
    for exec in execs {
        contents.push(format!("{}", exec.key))
    }

    Ok(contents.join("\n"))
}

fn create_cache() -> Result<(), Box<dyn Error>> {
    let cache_file_path = get_cache_file();

    if !Path::new(CACHE_DIR).exists() {
        fs::create_dir_all(CACHE_DIR)?;
    }

    let mut file = fs::OpenOptions::new()
        .write(true)
        .create(true)
        .open(cache_file_path)?;

    let cache_content = create_cache_content()?;
    file.write_all(cache_content.as_bytes())
        .expect("unable to write to cache");
    file.flush().expect("unable to flush file");
    Ok(())
}

fn main() {
    // decide if we should clear the aliases
    if get_does_cache_file_exist() && !get_is_subdirectory_of_cached_cwd() {
        let current_set_aliases = get_current_set_aliases().unwrap();
        print!("{}", current_set_aliases.join("; "));
        return;
    }

    // if we do not want to clear, we want to either set the aliases or ignore
    // if the config file does not exist then we don't have anything left to do
    if !get_does_config_file_exist() {
        return;
    }

    let execs = get_executables_from_config_file().unwrap();
    create_cache().unwrap();
    print!("{}", format_execs_as_alias_cmd_string(execs))
}
