
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- HTTP protocol support for all API endpoints (chat, embeddings, completions)
- HTTP support for both synchronous and asynchronous clients
- Environment variable support for HTTP base URLs (GRAVIXLAYER_BASE_URL)
- Comprehensive HTTP usage examples and test suite

### Changed
- Default base URL changed from HTTPS to HTTP for local development support
- Updated user agent version to match current package version (0.0.18)
- URL validation now accepts both HTTP and HTTPS protocols

### Fixed
- Version consistency between sync and async clients
- Removed hardcoded HTTPS-only restriction

## [0.0.15] - 2025-08-20

### Changed
- Version bump and maintenance updates

## [0.0.14] - 2025-08-20

### Changed
- Version bump and maintenance updates

## [0.0.13] - 2025-08-20

### Added
- Automated changelog generation during releases
- Release notes extraction for GitHub releases
- Enhanced release automation scripts

### Changed
- Improved release process workflow
- Updated GitHub Actions for better release management

### Fixed
- Release notes now properly populated from changelog
- Contributor information included in releases

## [0.0.12] - 2025-08-18

### Added
- Enhanced stream processing capabilities
- Improved error handling in completions

### Fixed
- JSON parsing improvements in completions.py
- SSE format handling in _create_stream method

## [0.0.11] - 2025-08-17

### Added
- Basic API implementation
- Stream processing capabilities

### Fixed
- Error handling enhancements

## [0.0.4] - 2024-12-XX

### Added
- Initial release with core functionality
- Basic OpenAI compatibility layer
- Authentication system

---

*Note: This changelog is automatically updated during releases. Add your changes to the [Unreleased] section.*