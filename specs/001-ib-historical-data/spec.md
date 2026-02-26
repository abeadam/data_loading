# Feature Specification: Historical Market Data Download from Interactive Brokers

**Feature Branch**: `001-ib-historical-data`
**Created**: 2026-02-26
**Status**: Draft
**Input**: User description: "Will download historical stock and futures data from interactive brokers"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Download Historical Stock Data (Priority: P1)

A researcher specifies a stock ticker, a date range, and a bar size (e.g., daily or
hourly). The system connects to Interactive Brokers, retrieves all available price bars
for that instrument over the requested period, and makes the data available for analysis
and modeling.

**Why this priority**: Historical stock data is the most common use case and delivers
immediate value for backtesting and analysis workflows. It establishes the core download
pattern that futures support builds on.

**Independent Test**: A researcher can request one year of daily OHLCV bars for a single
stock ticker and verify the returned dataset contains the correct number of trading days
with valid open, high, low, close, and volume fields.

**Acceptance Scenarios**:

1. **Given** a valid stock ticker, exchange, and a date range within IBKR's available
   history, **When** the researcher requests daily bars, **Then** the system returns a
   complete dataset of OHLCV bars for every trading day in that range.
2. **Given** a valid stock ticker, **When** the researcher requests intraday bars
   (e.g., hourly), **Then** the system returns bars aligned to market session hours with
   no gaps during trading hours.
3. **Given** a ticker that does not exist or lacks a market data subscription on IBKR,
   **When** a download is requested, **Then** the system reports a clear error that
   identifies the unknown instrument and does not silently return empty data.
4. **Given** a request where the start date exceeds IBKR's available history for the
   instrument, **When** the download runs, **Then** the system retrieves as much data as
   available and communicates the effective start date to the researcher.

---

### User Story 2 - Download Historical Futures Data (Priority: P2)

A researcher specifies a futures instrument, a date range, and a bar size. The system
retrieves historical price bars from Interactive Brokers and makes the data available
for analysis.

**Why this priority**: Futures data has additional complexity around contract
specification and builds on the stock download foundation established in US1.

**Independent Test**: A researcher can request several months of daily bars for a futures
instrument and verify the dataset contains valid OHLCV fields covering the requested
period.

**Acceptance Scenarios**:

1. **Given** a valid futures instrument specification and a date range, **When** the
   researcher requests daily bars, **Then** the system returns a complete OHLCV dataset
   for that instrument and period.
2. **Given** a futures instrument where the requested period spans a contract expiry
   boundary, **When** the download runs, **Then** the system automatically stitches
   adjacent contracts into a single continuous series, returning seamless OHLCV data
   across the full requested period without gaps at rollover dates.
3. **Given** a futures instrument with no available data for the requested period,
   **When** a download is attempted, **Then** the system reports a clear error rather
   than returning empty data silently.

---

### User Story 3 - Batch Download for Multiple Instruments (Priority: P3)

A researcher provides a list of instruments (stocks and/or futures) and a shared
configuration (date range, bar size). The system downloads data for all specified
instruments in a single operation and makes each dataset independently available.

**Why this priority**: Batch capability improves efficiency for portfolio-level research
but requires the single-instrument stories to be stable first.

**Independent Test**: A researcher can specify a list of three instruments and verify
that a separate dataset is returned for each, without requiring repeated manual
invocations or manual pacing management.

**Acceptance Scenarios**:

1. **Given** a list of valid instrument specifications and a shared date range, **When**
   a batch download is requested, **Then** the system retrieves and returns a dataset for
   each instrument.
2. **Given** a batch request where one instrument is invalid or unavailable, **When**
   the download runs, **Then** the system completes all valid downloads and reports
   which instruments failed, rather than aborting the entire batch.
3. **Given** a large batch that exceeds IBKR's rate limits, **When** the download runs,
   **Then** the system manages pacing automatically so the researcher does not need to
   introduce manual delays.

---

### Edge Cases

- What happens when the requested date range exceeds Interactive Brokers' maximum
  lookback limit for a given bar size?
- How does the system behave when the IBKR connection drops in the middle of a
  multi-instrument batch download?
- What is returned when the market was closed for the entire requested period (e.g.,
  a holiday week with no trading sessions)?
- How are partial bars handled when requesting intraday data that includes the current
  in-progress trading session?
- What happens when the same instrument is requested twice in a batch (duplicate entry)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST connect to an active Interactive Brokers session (TWS or IB
  Gateway) to retrieve data; it MUST NOT require a proprietary data feed or additional
  broker infrastructure.
- **FR-002**: System MUST accept a stock instrument specification (ticker symbol,
  exchange, currency) as input.
- **FR-003**: System MUST accept a futures instrument specification (symbol, exchange,
  currency) as input and MUST resolve it as a continuous/rolled series, automatically
  stitching adjacent contracts to produce a seamless price history across the full
  requested date range.
- **FR-004**: System MUST accept a date range (start date, end date) as input.
- **FR-005**: System MUST accept a bar size (e.g., daily, 1-hour, 15-minute, 1-minute)
  as input, limited to bar sizes natively supported by Interactive Brokers.
- **FR-006**: System MUST retrieve OHLCV (Open, High, Low, Close, Volume) bars for the
  specified instrument, date range, and bar size.
- **FR-007**: System MUST respect Interactive Brokers' pacing requirements, spacing
  requests automatically to avoid rate-limit errors without requiring caller intervention.
- **FR-008**: System MUST report clear, actionable errors when an instrument is not
  found, a subscription is missing, or the requested period is unavailable.
- **FR-009**: System MUST retry on temporary connection failures before surfacing an
  error to the caller.
- **FR-010**: System MUST support batch requests for multiple instruments, handling
  partial failures without aborting the full batch.
- **FR-011**: System MUST persist downloaded data to a user-configured local directory
  automatically. The output MUST be organized so that each instrument's data is
  retrievable independently by downstream processing modules.

### Key Entities

- **Instrument**: An asset to be downloaded — either a stock or a futures contract.
  Characterized by symbol, exchange, currency, and type (stock vs. futures).
- **Bar**: A single time-period price record containing open, high, low, close, and
  volume values, associated with a timestamp and bar size.
- **Download Request**: A specification combining one or more instruments, a date range,
  and a bar size.
- **Download Result**: The collection of bars returned for a completed download request,
  associated with the instrument and original request parameters.

## Assumptions

- An Interactive Brokers TWS or IB Gateway session is running and accessible on the
  local machine before the downloader is invoked. Session setup and credential management
  are out of scope.
- The IBKR account has active market data subscriptions for all requested instruments.
  Subscription management is out of scope.
- Bar sizes are limited to those natively available from the Interactive Brokers
  historical data API; custom resampling is out of scope for this feature.
- Recovery from account-level bans or subscription errors is out of scope; the system
  will surface these as clear errors.
- Futures data is always delivered as a continuous/rolled series. Retrieval of a single
  specific expiry contract is out of scope for this feature.
- The caller provides a writable local directory path for data persistence. Directory
  creation and disk space management are the caller's responsibility.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A researcher can request and receive one full year of daily bars for a
  single stock ticker in under 60 seconds on a stable connection.
- **SC-002**: A researcher can request intraday bars at any bar size supported by
  Interactive Brokers without writing any pacing or retry logic.
- **SC-003**: A batch request for up to 20 instruments completes successfully without
  the researcher manually managing rate limits or connection pacing.
- **SC-004**: When an instrument is invalid or unavailable, the system surfaces an error
  message that identifies the problem clearly enough for the researcher to correct the
  input without consulting IBKR API documentation.
- **SC-005**: A dropped connection during a batch download does not cause data already
  retrieved to be lost; the system retries the failed instrument and completes the batch.
