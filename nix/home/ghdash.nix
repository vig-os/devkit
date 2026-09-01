# vigos.ghdash — gh-dash PR/issue dashboard (#824). Parameterized port: the
# hardcoded personal repo filters became `repoFilters`; the CPU-tuning
# lessons (lean scoped sections, capped closed lists) are the defaults.
# Reuses the gh login; the gh-dash package rides this module (not devTools).
#
# Per-project scope and section profiles (#1586): `gh-dash-repo [profile]`
# launches the dashboard scoped to the repo of the directory it starts in —
# derived from `origin`, not declared, so nothing lands in project repos —
# and `profiles` names alternative section sets for projects whose workflow
# differs (sections are the one key gh-dash replaces rather than merges).
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.vigos.ghdash;

  scope = if cfg.repoFilters == [ ] then "involves:@me" else lib.concatStringsSep " " cfg.repoFilters;

  # The generated section set, parameterized over the scope so the same three
  # sections serve both the global settings (real scope, bare `gh-dash`
  # unchanged) and the wrapper's `default` template (placeholder scope).
  mkSections = scope': [
    {
      title = "Involved";
      filters = "is:open involves:@me ${scope'}";
    }
    {
      title = "Open";
      filters = "is:open ${scope'}";
    }
    {
      title = "Recently closed";
      filters = "is:closed ${scope'} sort:updated-desc";
      limit = 10;
    }
  ];

  sections = mkSections scope;

  # gh-dash has no template variable for "the current repo", so the wrapper
  # substitutes this token at launch time (sed over the rendered template).
  placeholder = "__GH_DASH_SCOPE__";

  # Profile authors write scope-free filters; the module appends the
  # placeholder — the same composition the generated sections use — so a
  # profile cannot silently ship unscoped (the idle-CPU cost the tuning
  # defaults exist to prevent).
  profileSections = map (
    s:
    {
      inherit (s) title;
      filters = "${s.filters} ${placeholder}";
    }
    // lib.optionalAttrs (s.limit != null) { inherit (s) limit; }
  );

  # Every wrapper-selectable template. `default` mirrors the generated
  # sections, so `gh-dash-repo` is valid with no profiles declared — and, as
  # with vigos.sesh layout profiles, it always wins over a same-named key.
  profileTemplates = lib.mapAttrs (_: profileSections) cfg.profiles // {
    default = mkSections placeholder;
  };

  # A template is the FULL merged settings with only the section keys
  # swapped, so consumer tuning (refetch interval, limits, layout) carries
  # into every per-repo config. Rendered as JSON — a subset of YAML, which
  # gh-dash reads fine — so the file text is eval-pure and assertable in
  # tests (a yaml generator would need a build).
  templateText =
    sections':
    builtins.toJSON (
      config.programs.gh-dash.settings
      // {
        prSections = sections';
        issuesSections = sections';
      }
    );

  # Launch gh-dash scoped to the repo of the current directory:
  #   gh-dash-repo [profile]
  # Repo comes from `origin` at the launch CWD; outside a GitHub repo the
  # scope falls back to `repoFilters` (or involves:@me), so the config is
  # always valid. The rendered config lives at a deterministic runtime path,
  # overwritten each launch — no cleanup, and `exec` is safe.
  ghDashRepo = pkgs.writeShellApplication {
    name = "gh-dash-repo";
    runtimeInputs = with pkgs; [
      git
      gnused
      gh-dash
      coreutils
      findutils
    ];
    text = ''
      profile="''${1:-default}"
      profiles_dir="''${XDG_CONFIG_HOME:-$HOME/.config}/gh-dash/profiles"
      src="$profiles_dir/$profile.yml"
      if [ ! -f "$src" ]; then
        printf 'gh-dash-repo: unknown profile %s\nValid profiles:%s\n' \
          "$profile" "$(find "$profiles_dir" -name '*.yml' -printf ' %f' | sed 's/\.yml//g')" >&2
        exit 1
      fi

      url=$(git config --get remote.origin.url 2>/dev/null || true)
      slug=""
      case "$url" in
        *github.com*)
          slug=$(printf '%s' "$url" | sed -E 's#^git@[^:]+:##; s#^https?://[^/]+/##; s#\.git$##')
          ;;
      esac
      if [ -n "$slug" ]; then
        sub="repo:$slug"
      else
        sub=${lib.escapeShellArg scope}
      fi

      dir="''${XDG_RUNTIME_DIR:-/tmp}/gh-dash"
      mkdir -p "$dir"
      conf="$dir/''${slug//\//-}-$profile.yml"
      sed "s#${placeholder}#$sub#g" "$src" > "$conf"
      exec gh-dash --config "$conf"
    '';
  };

  sectionModule = lib.types.submodule {
    options = {
      title = lib.mkOption {
        type = lib.types.str;
        description = "Section title shown in the dashboard.";
      };
      filters = lib.mkOption {
        type = lib.types.str;
        example = "is:open review-requested:@me";
        description = ''
          GitHub search filters, WITHOUT a repo/scope qualifier — the module
          appends the launch-time scope, exactly as the generated sections
          compose theirs.
        '';
      };
      limit = lib.mkOption {
        type = lib.types.nullOr lib.types.int;
        default = null;
        description = "Per-section row cap (null = gh-dash's default).";
      };
    };
  };
in
{
  options.vigos.ghdash = {
    enable = lib.mkEnableOption "the gh-dash PR/issue dashboard";
    repoFilters = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "repo:vig-os/devcontainer" ];
      description = ''
        GitHub search scope for the generated sections (e.g. repo:/org:
        qualifiers). Empty = everything involving you. Scoping to the repos
        you work in keeps each idle dashboard cheap. Also the fallback scope
        `gh-dash-repo` uses outside a GitHub repo.
      '';
    };
    profiles = lib.mkOption {
      type = lib.types.attrsOf (lib.types.listOf sectionModule);
      default = { };
      example = lib.literalExpression ''
        {
          shared = [
            {
              title = "Needs my review";
              filters = "is:open review-requested:@me";
            }
            {
              title = "Open";
              filters = "is:open";
            }
          ];
        }
      '';
      description = ''
        Named section sets selected per launch (`gh-dash-repo <name>`), for
        projects whose workflow differs from the generated three sections —
        a team repo wants review queues a solo repo has no use for. A
        {option}`vigos.sesh` layout profile can point its dashboard window at
        `gh-dash-repo <name>`, so selection rides the session entry that
        already identifies the project. The `default` profile is the
        generated section set and cannot be redefined here.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    programs.gh-dash = {
      enable = lib.mkDefault true;
      settings = {
        prSections = lib.mkDefault sections;
        issuesSections = lib.mkDefault sections;
        defaults.refetchIntervalMinutes = lib.mkDefault 10;
      };
    };

    home = {
      packages = [ ghDashRepo ];
      file = lib.mapAttrs' (
        name: sections':
        lib.nameValuePair ".config/gh-dash/profiles/${name}.yml" { text = templateText sections'; }
      ) profileTemplates;
    };
  };
}
